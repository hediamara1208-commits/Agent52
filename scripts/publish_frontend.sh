#!/usr/bin/env bash
# Build frontend/, write the runtime config.json, zip dist/, and publish to Amplify Hosting
# (manual deployment). Guidance-only app: this script only publishes static files.
#
# config.json holds apiUrl, userPoolId, userPoolClientId, region. No secrets.
# Values come from env (API_URL, USER_POOL_ID, USER_POOL_CLIENT_ID, AMPLIFY_APP_ID) or, when unset,
# from CloudFormation outputs of the stacks named below.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
AUTH_STACK="${GUIDE_AUTH_STACK:-GuideAuthStack}"
API_STACK="${GUIDE_API_STACK:-GuideApiStack}"
FRONTEND_STACK="${GUIDE_FRONTEND_STACK:-GuideFrontendStack}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

stack_output() { # stack, output key
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" --output text
}

need() { # name, value
  if [[ -z "$2" || "$2" == "None" ]]; then
    echo "publish_frontend: missing $1 (set the env var or deploy the stack first)" >&2
    exit 1
  fi
}

API_URL="${API_URL:-$(stack_output "$API_STACK" ApiUrl)}"
USER_POOL_ID="${USER_POOL_ID:-$(stack_output "$AUTH_STACK" UserPoolId)}"
USER_POOL_CLIENT_ID="${USER_POOL_CLIENT_ID:-$(stack_output "$AUTH_STACK" UserPoolClientId)}"
APP_ID="${AMPLIFY_APP_ID:-$(stack_output "$FRONTEND_STACK" AmplifyAppId)}"
BRANCH="${AMPLIFY_BRANCH:-$(stack_output "$FRONTEND_STACK" AmplifyBranchName)}"
need API_URL "$API_URL"
need USER_POOL_ID "$USER_POOL_ID"
need USER_POOL_CLIENT_ID "$USER_POOL_CLIENT_ID"
need AMPLIFY_APP_ID "$APP_ID"
need AMPLIFY_BRANCH "$BRANCH"

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then npm ci; fi
npm run build

# Runtime config, read by the UI at /config.json.
python3 - "$ROOT/frontend/dist/config.json" "$API_URL" "$USER_POOL_ID" "$USER_POOL_CLIENT_ID" "$REGION" <<'PY'
import json, sys
path, api_url, pool, client, region = sys.argv[1:6]
with open(path, "w") as fh:
    json.dump({"apiUrl": api_url, "userPoolId": pool, "userPoolClientId": client, "region": region}, fh, indent=2)
    fh.write("\n")
PY

ZIP="$(mktemp -d)/frontend.zip"
(cd dist && python3 -m zipfile -c "$ZIP" . >/dev/null)

read -r JOB_ID ZIP_URL < <(aws amplify create-deployment --region "$REGION" \
  --app-id "$APP_ID" --branch-name "$BRANCH" \
  --query '[jobId, zipUploadUrl]' --output text)
curl --fail --silent --show-error -X PUT -H "Content-Type: application/zip" --data-binary "@$ZIP" "$ZIP_URL"
aws amplify start-deployment --region "$REGION" --app-id "$APP_ID" --branch-name "$BRANCH" --job-id "$JOB_ID" >/dev/null

UI_URL="$(stack_output "$FRONTEND_STACK" UiUrl 2>/dev/null || true)"
echo "Published job $JOB_ID. UI: ${UI_URL:-https://$BRANCH.$APP_ID.amplifyapp.com}"
