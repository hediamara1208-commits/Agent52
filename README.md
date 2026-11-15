# Agentic Investment Guide

Simulation only. This project gives no investment advice and makes no predictions. It only guides: it never places an order, moves money, or holds credentials.

## Jury credentials

The deployed UI requires Cognito sign-in. After `make deploy`, create the jury account:

```bash
export DEMO_USER_EMAIL="jury@example.com"
read -rs DEMO_USER_PASSWORD && export DEMO_USER_PASSWORD
bash scripts/create_demo_user.sh
```

- The password comes only from the `DEMO_USER_PASSWORD` environment variable. It is never written to a file, committed, or logged. Give it to the jury through a separate channel.
- The script finds the user pool from the `UserPoolId` output of the stack in `AUTH_STACK_NAME` (default `GuideAuthStack`). Set `USER_POOL_ID` to skip that lookup.
- Re-running the script resets the password of the existing user.
- Region defaults to `us-east-1`.
