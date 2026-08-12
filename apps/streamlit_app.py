"""Recruiter-friendly local UI that communicates only with the FastAPI backend."""

import streamlit as st

from financial_rag.core.errors import BenchmarkImportError
from financial_rag.demo import (
    DemoApiError,
    DemoSettings,
    FinancialRagApiClient,
    ModeComparison,
    available_scores,
    refresh_submitted_job,
    source_label,
    top_chunk_overlap,
)
from financial_rag.domain.evaluation import EvaluationConfig, EvaluationReport
from financial_rag.domain.generation import CitationContext, GroundedAnswer
from financial_rag.domain.indexing import CorpusBuildJob, UploadDocument
from financial_rag.domain.retrieval import RetrievalMode, RetrievedChunk
from financial_rag.evaluation.importers import parse_benchmark_bytes

MODE_LABELS = {
    RetrievalMode.DENSE: "Dense",
    RetrievalMode.HYBRID: "Hybrid",
    RetrievalMode.HYBRID_RERANKED: "Hybrid + reranker",
}


def _mode_selector(label: str, *, key: str) -> RetrievalMode:
    value = st.selectbox(
        label,
        options=list(RetrievalMode),
        format_func=lambda mode: MODE_LABELS[mode],
        index=1,
        key=key,
    )
    return RetrievalMode(value)


def _render_score_line(chunk: RetrievedChunk) -> None:
    scores = available_scores(chunk)
    if not scores:
        st.caption("No component scores returned.")
        return
    st.caption(" · ".join(f"{score.label}: {score.value:.4f}" for score in scores))


def _render_chunk(chunk: RetrievedChunk, *, title_prefix: str = "Rank") -> None:
    with st.expander(f"{title_prefix} {chunk.rank} — {source_label(chunk)}"):
        _render_score_line(chunk)
        st.caption(f"Chunk ID: {chunk.chunk_id}")
        st.text(chunk.content)


def _render_citation(context: CitationContext) -> None:
    chunk = context.chunk
    with st.expander(f"[{context.citation_id}] {source_label(chunk)}"):
        if context.content_truncated:
            st.caption("The generation context was truncated by the configured context budget.")
        st.caption(f"Chunk ID: {chunk.chunk_id} · retrieval rank: {chunk.rank}")
        st.text(context.content)


def _render_answer(answer: GroundedAnswer) -> None:
    if answer.abstained:
        st.warning(answer.answer)
    else:
        st.markdown(answer.answer)

    st.caption(
        f"Mode: {MODE_LABELS[answer.retrieval.mode]} · Model: {answer.model_identifier} · "
        f"Citations: {len(answer.citations)}"
    )
    if answer.usage.total_tokens is not None:
        st.caption(
            "Provider usage — "
            f"input: {answer.usage.input_tokens}, output: {answer.usage.output_tokens}, "
            f"total: {answer.usage.total_tokens}"
        )

    st.subheader("Citations")
    if not answer.contexts:
        st.info("No context was retrieved; the answer used the local abstention policy.")
    for context in answer.contexts:
        _render_citation(context)

    st.subheader("Retrieved chunks and score trace")
    for chunk in answer.retrieval.chunks:
        _render_chunk(chunk)


def _render_comparison(comparison: ModeComparison) -> None:
    columns = st.columns(3)
    successful = []
    for column, item in zip(columns, comparison.items, strict=True):
        with column:
            st.subheader(MODE_LABELS[item.mode])
            if item.failure is not None:
                st.error(item.failure.message)
                st.caption(f"Error code: {item.failure.code}")
                continue
            assert item.result is not None
            successful.append(item.result)
            st.metric("Chunks returned", len(item.result.chunks))
            for chunk in item.result.chunks[:5]:
                _render_chunk(chunk, title_prefix="#")

    if len(successful) > 1:
        st.subheader("Top-result overlap")
        rows = []
        for left_index, left in enumerate(successful):
            for right in successful[left_index + 1 :]:
                rows.append(
                    {
                        "Pair": f"{MODE_LABELS[left.mode]} vs {MODE_LABELS[right.mode]}",
                        "Jaccard overlap": top_chunk_overlap(left.chunks, right.chunks),
                    }
                )
        st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_sidebar(client: FinancialRagApiClient, settings: DemoSettings) -> None:
    with st.sidebar:
        st.header("Local demo")
        st.caption(f"FastAPI: {settings.financial_rag_api_url}")
        if st.button("Check backend", use_container_width=True):
            try:
                readiness = client.readiness()
            except DemoApiError as exc:
                st.error(str(exc))
            else:
                if readiness.components.retrieval.value == "ready":
                    st.success("Retrieval is ready")
                else:
                    st.warning("Retrieval is not configured")
                st.caption(
                    "Generation: "
                    f"{readiness.components.generation.value} · "
                    f"Revisions: {readiness.components.revisions.value}"
                )
                st.caption(f"Document lifecycle: {readiness.components.indexing.value}")
        st.divider()
        st.caption(
            "Local, single-user development demo. Answers may be incorrect and are not "
            "financial or investment advice."
        )


def _ask_tab(client: FinancialRagApiClient) -> None:
    st.header("Ask the configured corpus")
    st.caption("Answers include request-local citations and the underlying retrieval trace.")
    with st.form("grounded-question"):
        query = st.text_area(
            "Question",
            placeholder="What were the capital expenditures and how did they change?",
            max_chars=4096,
        )
        mode = _mode_selector("Retrieval mode", key="answer-mode")
        submitted = st.form_submit_button("Generate grounded answer", type="primary")
    if submitted:
        try:
            with st.spinner("Retrieving evidence and generating an answer…"):
                st.session_state["grounded_answer"] = client.answer(query, mode=mode)
        except (DemoApiError, ValueError) as exc:
            st.error(str(exc))
            st.session_state.pop("grounded_answer", None)
    answer = st.session_state.get("grounded_answer")
    if isinstance(answer, GroundedAnswer):
        _render_answer(answer)


def _compare_tab(client: FinancialRagApiClient) -> None:
    st.header("Compare retrieval modes")
    st.caption("The identical query is sent to dense, hybrid, and hybrid + reranker.")
    with st.form("mode-comparison"):
        query = st.text_area(
            "Comparison question",
            placeholder="What was the year-end net PP&E balance?",
            max_chars=4096,
        )
        submitted = st.form_submit_button("Run three-mode comparison", type="primary")
    if submitted:
        try:
            with st.spinner("Running the controlled comparison…"):
                st.session_state["mode_comparison"] = client.compare_retrieval(query)
        except ValueError as exc:
            st.error(str(exc))
            st.session_state.pop("mode_comparison", None)
    comparison = st.session_state.get("mode_comparison")
    if isinstance(comparison, ModeComparison):
        _render_comparison(comparison)


def _render_evaluation(report: EvaluationReport) -> None:
    st.caption(
        f"Run: {report.manifest.evaluation_run_id} · Dataset: {report.manifest.dataset_id} · "
        f"Queries: {report.manifest.query_count}"
    )
    aggregate_rows = []
    for aggregate in report.aggregates:
        row = {
            "Mode": MODE_LABELS[aggregate.mode],
            "Completed": aggregate.retrieval_completed,
            "Failed": aggregate.retrieval_failed,
            "MRR": aggregate.mrr,
            "Exact match": aggregate.exact_match,
            "Token F1": aggregate.token_f1,
        }
        row.update({f"Hit@{metric.k}": metric.value for metric in aggregate.hit_at_k})
        aggregate_rows.append(row)
    st.dataframe(aggregate_rows, hide_index=True, use_container_width=True)

    with st.expander("Per-query status and metrics"):
        item_rows = [
            {
                "Query ID": item.query_id,
                "Mode": MODE_LABELS[item.mode],
                "Retrieval": item.retrieval_status.value,
                "First relevant rank": item.first_relevant_rank,
                "Reciprocal rank": item.reciprocal_rank,
                "Answer": item.answer_status.value,
                "Exact match": item.exact_match,
                "Token F1": item.token_f1,
            }
            for item in report.items
        ]
        st.dataframe(item_rows, hide_index=True, use_container_width=True)


def _evaluation_tab(client: FinancialRagApiClient) -> None:
    st.header("Evaluate retrieval")
    st.caption(
        "Upload a small platform_eval_dataset_v1 JSON or JSONL file. The file is parsed in "
        "memory and sent to FastAPI; it is not persisted by this UI."
    )
    uploaded = st.file_uploader(
        "Benchmark file",
        type=("json", "jsonl"),
        accept_multiple_files=False,
        help="Maximum contract size: 500 query items and 5 MiB.",
    )
    hit_ks = st.multiselect(
        "Hit@K cutoffs",
        options=(1, 3, 5, 10, 20),
        default=(1, 3, 5, 10),
    )
    include_answers = st.checkbox(
        "Include deterministic answer metrics",
        help="Requires reference answers in the benchmark and configured backend generation.",
    )
    if st.button("Run paired evaluation", type="primary", disabled=uploaded is None):
        assert uploaded is not None
        try:
            dataset = parse_benchmark_bytes(
                uploaded.getvalue(),
                filename=uploaded.name,
            )
            config = EvaluationConfig(
                hit_ks=tuple(sorted(hit_ks)),
                include_answer_metrics=include_answers,
            )
            with st.spinner("Evaluating the identical query set across all modes…"):
                st.session_state["evaluation_report"] = client.evaluate(dataset, config=config)
        except (BenchmarkImportError, DemoApiError, ValueError) as exc:
            st.error(str(exc))
            st.session_state.pop("evaluation_report", None)
    report = st.session_state.get("evaluation_report")
    if isinstance(report, EvaluationReport):
        _render_evaluation(report)


def _documents_tab(client: FinancialRagApiClient) -> None:
    st.header("Build and select a local corpus")
    st.caption(
        "Upload up to 10 PDF, Markdown, or text files. Files are staged locally, indexed "
        "in an in-process job, and removed from staging when the job finishes."
    )
    uploaded_files = st.file_uploader(
        "Financial documents",
        type=("pdf", "md", "txt"),
        accept_multiple_files=True,
        help="20 MiB per file, 50 MiB total. PDF extraction is text-only; OCR is not included.",
    )
    label = st.text_input("Corpus label (optional)", max_chars=200)
    if st.button(
        "Upload and build corpus",
        type="primary",
        disabled=not uploaded_files,
    ):
        try:
            documents = tuple(
                UploadDocument(filename=item.name, content=item.getvalue())
                for item in uploaded_files
            )
            with st.spinner("Submitting the bounded local corpus build…"):
                st.session_state["submitted_corpus_job"] = client.upload_documents(
                    documents,
                    label=label or None,
                )
            st.success("Corpus build accepted. Refresh job status below.")
        except (DemoApiError, ValueError) as exc:
            st.error(str(exc))

    if st.button("Refresh jobs and revisions", use_container_width=True):
        try:
            jobs = client.list_corpus_jobs()
            st.session_state["corpus_jobs"] = jobs
            st.session_state["index_revisions"] = client.list_index_revisions()
            submitted = st.session_state.get("submitted_corpus_job")
            if isinstance(submitted, CorpusBuildJob):
                st.session_state["submitted_corpus_job"] = refresh_submitted_job(submitted, jobs)
        except DemoApiError as exc:
            st.error(str(exc))

    submitted = st.session_state.get("submitted_corpus_job")
    if isinstance(submitted, CorpusBuildJob):
        st.caption(f"Submitted job: {submitted.job_id} · status: {submitted.status.value}")

    jobs = st.session_state.get("corpus_jobs", ())
    if jobs:
        st.subheader("Recent build jobs")
        st.dataframe(
            [
                {
                    "Job": job.job_id,
                    "Label": job.label,
                    "Status": job.status.value,
                    "Files": job.input_file_count,
                    "Corpus revision": job.corpus_revision_id,
                    "Index revision": job.index_revision_id,
                    "Error code": job.error_code,
                }
                for job in jobs
            ],
            hide_index=True,
            use_container_width=True,
        )

    indexes = st.session_state.get("index_revisions", ())
    if indexes:
        st.subheader("Select an index revision")
        ready_indexes = [item.index_revision_id for item in indexes if item.status == "ready"]
        if not ready_indexes:
            st.info("No ready index revision is available.")
            return
        selected = st.selectbox(
            "Ready index",
            options=ready_indexes,
        )
        if st.button("Activate selected index"):
            try:
                activated = client.activate_index(selected)
                st.success(f"Activated {activated.index_revision_id}")
            except DemoApiError as exc:
                st.error(str(exc))


def main() -> None:
    """Render the local demo without opening backend/model/database connections directly."""
    st.set_page_config(
        page_title="Financial RAG Platform",
        page_icon="📄",
        layout="wide",
    )
    settings = DemoSettings()
    client = FinancialRagApiClient(settings)
    st.title("Financial Document Intelligence")
    st.caption("Inspect the evidence behind every answer and compare retrieval strategies.")
    _render_sidebar(client, settings)

    documents_tab, ask_tab, compare_tab, evaluation_tab, scope_tab = st.tabs(
        ("Documents", "Ask", "Compare retrieval", "Evaluate", "Current scope")
    )
    with documents_tab:
        _documents_tab(client)
    with ask_tab:
        _ask_tab(client)
    with compare_tab:
        _compare_tab(client)
    with evaluation_tab:
        _evaluation_tab(client)
    with scope_tab:
        st.header("Honest demo boundary")
        st.markdown(
            """
            This interface calls the FastAPI backend only. It never receives an OpenAI API key
            and does not import the database, FAISS index, or model adapters.

            Document upload and corpus/index selection use bounded local staging and durable
            PostgreSQL job metadata. Execution remains in-process and is not resumable after a
            crash; interrupted jobs are marked failed on the next startup.

            This is an in-development local demonstration, not a public or production service.
            """
        )


if __name__ == "__main__":
    main()
