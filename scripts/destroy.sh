#!/usr/bin/env bash
# Destroy every stack. The Primary_Store bucket has a RETAIN policy, so the dataset survives.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
cd "$ROOT/infra"
# shellcheck disable=SC2086
npx -y aws-cdk@2 --app "${PYTHON:-python} app.py" destroy --all --force ${CDK_ARGS:-}
echo "destroy: stacks removed; the Primary_Store bucket is retained (delete it by hand if you want it gone)."
