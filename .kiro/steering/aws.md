---
inclusion: fileMatch
fileMatchPattern: "infra/**|requirements.md"
---

# AWS rules (only when editing infra/ or AWS-related code)

## MVP services (deployed by `make deploy`)

| Service | Role |
|---------|------|
| Amplify Hosting | React UI |
| Cognito | Sign-in and JWTs |
| API Gateway | Session_API REST |
| Lambda | API handlers |
| DynamoDB | Session_Store (7-day TTL) |
| Bedrock AgentCore Runtime | Agent hosting |
| S3 | Primary data store (versioned, deny-delete) |
| Glue | Data Catalog |
| Athena | Validation queries only |
| CloudWatch | Logs (30-day retention) |

## Stretch services (optional, context flags)

- AgentCore Gateway (MCP tools)
- AgentCore Identity (JWT inbound)
- WAF (managed rules)
- KMS (customer key)
- CloudTrail data events
- S3 Object Lock
- EventBridge + Step Functions (snapshot pipeline)
- Budgets + alarms

## CDK app

- Single command deploy: `cdk deploy --all`
- Python CDK v2
- Region: `us-east-1`
- Least-privilege IAM by default

## Requirement mapping

- **Tier 2 AWS**: 8.1-8.9, 17.1-17.3, 17.14, 18.1-18.5, 18.7-18.9, 19.2, 19.5-19.8, 20.1, 20.4-20.7, 20.11, 22, 23.1-23.6, 25.3, 25.6, 26.1-26.5, 26.7
- **Tier 3 AWS**: Everything else

## AWS service map

See `design.md` section "AWS service map" for complete status.
