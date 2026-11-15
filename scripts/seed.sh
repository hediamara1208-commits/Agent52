#!/usr/bin/env bash
# Load the committed dataset into the deployed Primary_Store bucket and seed the Precedents.
#   DATA_STACK_NAME   default GuideDataStack
#   API_STACK_NAME    default GuideApiStack
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGION="${AWS_REGION:-us-east-1}"
PY="${PYTHON:-python}"
out() { aws cloudformation describe-stacks --region "$REGION" --stack-name "$1" \
  --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" --output text; }
BUCKET="$(out "${DATA_STACK_NAME:-GuideDataStack}" PrimaryStoreBucket)"
TABLE="$(out "${API_STACK_NAME:-GuideApiStack}" SessionTableName)"
for v in "$BUCKET" "$TABLE"; do
  if [[ -z "$v" || "$v" == "None" ]]; then echo "seed: deploy the stacks first (make deploy)" >&2; exit 1; fi
done
cd "$ROOT"
GUIDE_S3_BUCKET="$BUCKET" "$PY" -m guide.ingest.seed
GUIDE_S3_BUCKET="$BUCKET" "$PY" scripts/seed_precedents.py --table "$TABLE"
echo "seed: snapshot written to s3://$BUCKET and precedents written to $TABLE"
