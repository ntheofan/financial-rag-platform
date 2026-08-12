"""Safe JSON export for evaluation reports that contain no source or answer text."""

from pathlib import Path

from financial_rag.core.errors import EvaluationError
from financial_rag.domain.evaluation import EvaluationReport


def write_evaluation_report(
    report: EvaluationReport,
    path: Path,
    *,
    overwrite: bool = False,
) -> None:
    """Write one explicit JSON report without silently replacing an existing run."""
    if path.suffix.casefold() != ".json":
        raise EvaluationError("Evaluation report output must use a .json extension.")
    if path.exists() and not overwrite:
        raise EvaluationError("Evaluation report output already exists.")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        raise EvaluationError("Unable to write the evaluation report.") from exc
