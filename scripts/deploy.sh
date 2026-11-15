#!/usr/bin/env bash
# Deploy every MVP stack in order, then publish the front end. Uses the AWS credential chain only.
#   CDK_ARGS   extra CDK context, e.g. CDK_ARGS="-c budget_email=me@example.com -c enable_identity=true"
#   Docker is required (the Agent_Runtime image is built by CDK).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
STACKS=(GuideDataStack GuideFrontendStack GuideAuthStack GuideRuntimeStack GuideApiStack GuideOpsStack)
CDK=(npx -y aws-cdk@2 --app "${PYTHON:-python} app.py")

bash "$ROOT/scripts/build_api_deps.sh"
cd "$ROOT/infra"
# shellcheck disable=SC2086
"${CDK[@]}" deploy "${STACKS[@]}" --require-approval never --concurrency 1 ${CDK_ARGS:-}
bash "$ROOT/scripts/publish_frontend.sh"
echo "deploy: done. Next: make seed, then scripts/create_demo_user.sh"
