# Official IFEval provenance

Source: https://github.com/google-research/google-research/tree/e6890f85757dd84e27ca6df2dd30651dafad28e0/instruction_following_eval

Commit: `e6890f85757dd84e27ca6df2dd30651dafad28e0`

The original dataset, Python scorer, registry, utilities, tests, README and requirements are retained without edits. File SHA256 values are in `manifest.json`. The repository's Apache-2.0 license is retained as `LICENSE`; copyright headers remain in the source files.

The adapter adds persistence and reporting, seeds Python random / langdetect at 0 for reproducible rescoring, and uses NLTK 3.9.1 with the punkt_tab resource. It does not change the official checker rules. `requirements.txt` upstream calls the distribution `absl`; this project correctly installs `absl-py`.

Provider protocol references checked on 2026-09-26:

- https://api-docs.deepseek.com/api/create-chat-completion/
- https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions

API availability, permissions, geographic endpoint and account billing have not been tested against a live model service.
