# Grounded generation and citations

## Retrieval-to-answer flow

`GroundedGenerationService` uses the existing `RetrievalUseCase` and therefore
preserves the reproducible `dense`, `hybrid`, and `hybrid_reranked` comparison.
For each question it:

1. runs the selected retrieval mode;
2. selects up to the first five ranked chunks without reordering them;
3. assigns stable request-local labels `C1` through `C5`;
4. applies a checked-in 6,000-token context budget using a documented offline
   whitespace-token estimate;
5. sends the bounded prompt to an injected generation adapter;
6. rejects duplicate, missing, or unknown model-supplied citation IDs;
7. maps accepted IDs back to document, chunk, file, page, section, and retrieval
   rank lineage.

The API response includes the answer, abstention flag, validated citations,
the exact contexts exposed to the model, the complete retrieval result and
scores, the model identifier, and provider token usage when available.

The whitespace counter is deterministic and dependency-free, but it is not the
provider's billing tokenizer. The OpenAI request remains subject to the model's
actual context limits. The assembler truncates only the final selected context
when necessary and marks that context with `content_truncated=true`.

## Generation boundary

The OpenAI adapter uses the official Python SDK and the Responses API structured
output parser with a Pydantic `ModelAnswer` schema. The default local model is
configurable through `OPENAI_MODEL`; request timeout, retry count, and output
token limit are also explicit. The API key is accepted only as a Pydantic
`SecretStr` from local environment settings. No key is read or client created at
module import time, and `store=false` is sent on generation requests.

The prompt treats retrieved document content as untrusted evidence and requires
abstention when it is insufficient. An empty retrieval result is handled by a
local abstention policy without calling a model.

## What citation validation guarantees

Validation guarantees that every returned citation points to a chunk that was
actually supplied in this request's top-five context, and that every
non-abstained answer has at least one such citation. It does not prove that each
natural-language claim is entailed by the cited text. Claim-level entailment,
quote-span verification, and answer-quality evaluation remain later work, so
this phase makes no correctness or benchmark claim.

Automated tests inject fake generation clients and never make a live OpenAI
request. A real request occurs only when a local operator explicitly configures
both retrieval artifacts and `OPENAI_API_KEY`, starts the local runtime, and
calls `POST /api/v1/query`.
