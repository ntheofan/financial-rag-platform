# Data licensing and attribution

The MIT license in [LICENSE](LICENSE) applies only to original software and
documentation created for `financial-rag-platform`. It does not relicense any
dataset, filing, model, model output, or third-party content.

## FinanceBench

The research notebooks were developed against the open-source FinanceBench
sample published by Patronus AI:

- Dataset: <https://huggingface.co/datasets/PatronusAI/financebench>
- Official repository: <https://github.com/patronus-ai/financebench>
- Paper: <https://arxiv.org/abs/2311.11944>

The Hugging Face dataset card identifies the dataset license as Creative
Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0). Users must
review and comply with that license, including its attribution and
non-commercial-use conditions.

Suggested academic citation:

```bibtex
@misc{islam2023financebench,
  title         = {FinanceBench: A New Benchmark for Financial Question Answering},
  author        = {Pranab Islam and Anand Kannappan and Douwe Kiela and
                   Rebecca Qian and Nino Scherrer and Bertie Vidgen},
  year          = {2023},
  eprint        = {2311.11944},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CL}
}
```

## Source financial documents

Financial filings and investor-relations PDFs may be publicly accessible, but
public accessibility does not automatically grant a blanket right to
redistribute every source file or every derived full-text copy. This project
therefore does not publish source PDFs, parsed JSON, extracted Markdown,
cleaned full text, generated contexts, embeddings, or vector indexes.

Future import tooling will direct users to official sources. Each user remains
responsible for verifying the terms that apply to documents they download or
upload.

## Repository boundary

The public repository may include only synthetic test fixtures and data that
has been separately cleared for publication. Local FinanceBench files and all
derived artifacts are excluded by `.gitignore` and governed by
[docs/publication-policy.md](docs/publication-policy.md).

This document records the project's publication policy and is not legal
advice.
