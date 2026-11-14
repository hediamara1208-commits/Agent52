---
inclusion: fileMatch
fileMatchPattern: "config.yaml|guide/config.py"
---

# Config rules (only when editing config.yaml or guide/config.py)

## Key values (no defaults, no credentials)

| Key | Type | Purpose |
|-----|------|---------|
| `aws_region` | string | AWS region (us-east-1) |
| `model_id` | string | Bedrock model ID (e.g., `us.amazon.nova-pro-v1:0`) |
| `guardrail_id` | string | Bedrock guardrail ID |
| `guardrail_version` | string | Guardrail version (`DRAFT` or specific) |
| `s3_bucket` | string | Primary data store (required) |
| `s3_prefix` | string | Data prefix within bucket |
| `cache_dir` | string | Local cache directory (`.gitignore`) |
| `glue_database` | string | Glue Data Catalog database |
| `athena_workgroup` | string | Athena workgroup name |
| `athena_results_uri` | string | Athena results bucket URI |
| `seed_dir` | string | Starter CSV directory |
| `persona_file` | string | Path to `personas.yaml` |
| `instruction_dir` | string | Path to `agents/instructions` |
| `session_table` | string | DynamoDB session table |
| `agent_runtime_arn` | string | AgentCore Runtime ARN |
| `sensitivity_ranges` | object | Position size and horizon ranges |
| `speculative_volatility_threshold` | float | Speculative asset threshold |
| `trace_summary_max_chars` | int | Summary length cap |
| `cors_origin` | string | Amplify app URL |

## Rules

- **No credential fields**: Use AWS credential chain and roles
- **Log redaction**: Filter AWS key patterns from logs
- **Environment override**: `GUIDE_*` env vars override YAML values
- **S3-primary**: `data_location` and `data_dir` are rejected; S3 is always source
- **Macro lags**: Defined per series ID in config

## Example

```yaml
aws_region: us-east-1
model_id: us.amazon.nova-pro-v1:0
guardrail_id: gr-abc123
guardrail_version: DRAFT
s3_bucket: my-guide-data
s3_prefix: dataset
cache_dir: /workshop/Agent52/.cache/dataset
seed_dir: /workshop/Agent52/data
```
