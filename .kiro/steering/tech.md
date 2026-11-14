---
inclusion: always
---
# Tech stack

- Python 3.11, pandas, Streamlit, boto3, jsonschema, pytest (hypothesis only for Properties 10, 12, 13, 17, 24).
- AWS region `us-east-1`. Models via Bedrock Converse: Judge and Clerk `us.anthropic.claude-sonnet-4-5-20250929-v1:0`; Prosecutor and Defense `us.anthropic.claude-haiku-4-5-20251001-v1:0` (check the exact IDs in the Bedrock console before use).
- Every Bedrock call passes `guardrailConfig`. Retry throttling 3 times with exponential backoff.
- No credentials in code, config, or logs. Credentials come from the AWS default chain (role).
- Never commit `__pycache__`, `.env`, or AWS keys.
