#!/usr/bin/env bash
# Create (or reset) the jury demo user in the Cognito user pool.
#
# The password is read from the environment and is never stored, echoed, or committed.
#   DEMO_USER_PASSWORD   required, set it in your shell before running
#   DEMO_USER_EMAIL      required, the sign-in email for the jury account
#   USER_POOL_ID         optional, otherwise read from the CloudFormation output
#                        UserPoolId of the stack named in AUTH_STACK_NAME
#   AUTH_STACK_NAME      optional, default GuideAuthStack
#   AWS_REGION           optional, default us-east-1
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
: "${DEMO_USER_EMAIL:?Set DEMO_USER_EMAIL to the jury sign-in email}"
: "${DEMO_USER_PASSWORD:?Set DEMO_USER_PASSWORD in the environment (never commit it)}"

if [[ -z "${USER_POOL_ID:-}" ]]; then
  STACK="${AUTH_STACK_NAME:-GuideAuthStack}"
  USER_POOL_ID="$(aws cloudformation describe-stacks \
    --region "$REGION" --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue | [0]" \
    --output text)"
fi
if [[ -z "$USER_POOL_ID" || "$USER_POOL_ID" == "None" ]]; then
  echo "create_demo_user: could not determine the user pool id" >&2
  exit 1
fi

# Create the user without sending an invitation email; ignore "already exists".
if ! aws cognito-idp admin-create-user \
  --region "$REGION" --user-pool-id "$USER_POOL_ID" \
  --username "$DEMO_USER_EMAIL" \
  --user-attributes "Name=email,Value=$DEMO_USER_EMAIL" "Name=email_verified,Value=true" \
  --message-action SUPPRESS >/dev/null 2>&1; then
  echo "create_demo_user: user exists or creation failed, resetting the password" >&2
fi

# Set a permanent password so the jury is not forced through a change-password step.
aws cognito-idp admin-set-user-password \
  --region "$REGION" --user-pool-id "$USER_POOL_ID" \
  --username "$DEMO_USER_EMAIL" \
  --password "$DEMO_USER_PASSWORD" --permanent >/dev/null

echo "create_demo_user: demo user $DEMO_USER_EMAIL is ready in pool $USER_POOL_ID"
