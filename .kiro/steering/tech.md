---
inclusion: always
---
# Tech stack

- Backend: Python 3.11, pandas, pyarrow, boto3, jsonschema, pytest (hypothesis only where a task asks for it).
- Front end: React, TypeScript, Vite, Vitest; types generated from `session_view.schema.json`.
- Infrastructure: AWS CDK v2 in Python, region `us-east-1`.
- Models via Bedrock Converse with `guardrailConfig` on every call; model IDs are already in `config.yaml` (US inference profile `us.anthropic.claude-sonnet-5-5`, tested on the event account). Retry throttling 3 times with exponential backoff.
- One entry point `run_session` for the runtime, the tests, and `python -m guide.run_session`.
- No credentials in code, config, logs, or the front-end bundle. Never commit `__pycache__`, `.env`, or AWS keys.
