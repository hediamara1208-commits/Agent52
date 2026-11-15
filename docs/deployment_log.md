# Deployment log (event account, 2026-11-14/15)

During the event, some changes went straight to AWS instead of through `make deploy`, because they had to land fast and one-by-one. This page lists each of them so the live stack can be explained and rebuilt. Everything here is also in `main` as code, except where a row says otherwise.

Region `us-east-1`. Nothing below is a secret: IDs and names only.

## What is live now

| Piece | Live value | Source in `main` |
|---|---|---|
| AgentCore Runtime `guide_runtime-SeZKjzHUQD` | version 23, image tag `agents-run14` | `guide/`, `runtime/`, `config.yaml` as of PR #34 |
| Session_API Lambda `guide-session-api` | code edited by hand twice on 2026-11-15 (see below) | `api/`, `guide/contract/` at `main` (PR #34) |
| Amplify app `d3nprpi8xxns73`, branch `main` | Deployment 8, uploaded by hand | `frontend/` as of PR #34 |
| Bedrock Guardrail `3981l0ehd4uu` | DRAFT, prompt-attack filter only (HIGH, input) | **differs from** `infra/stacks/guardrail_stack.py` (see below) |
| Dataset snapshot (S3 `alphaforge-guide-data`, prefix `dataset`) | `20261115T154221Z-esg` | made by `scripts/add_reference_table.py` |
| Runtime role `guide-application-role` | has `bedrock-agentcore:InvokeWebSearch` | `infra/iam.py` (`AgentCoreWebSearch` statement) |

## Runtime versions

Each image adds one layer on top of the previous one (`FROM <previous tag>` + `COPY app/ /app/`), because the runtime image is arm64 and the build hosts were x86 (no `RUN` step possible). The `app/` folder holds `guide/`, `runtime/` and `config.yaml` as in `runtime/Dockerfile`.

| Runtime version | Image tag | Code | What changed |
|---|---|---|---|
| 15 | `agents-run6` | `06f3520` (PR #20) | Judge decides, Newsroom (web search), ESG list, 0% = reject. The 30-session benchmark ran on this version. |
| 16 | `agents-run7` | PR #22 to #24 | Personas accept `very_high` (Kai); case-study fallback base; `recent_context` in the SessionView schema; news filter (promos, asset name, clean snippets, 2 per site) |
| 17 | `agents-run8` | PR #25 | Buy questions dropped; sources are sites not servers; bylines and datelines removed |
| 18 | `agents-run9` | PR #26 | Contact lines and email addresses removed from snippets |
| 19 | `agents-run10` | PR #27 | One card per headline; stray symbols trimmed |
| 20 | `agents-run11` | PR #28 | More forecast wordings dropped ("turn bullish", "poised for", "could hit $X") |
| 21 | `agents-run12` | PR #30 | The Advocate may propose a compliant request as is (Robert 2% SPY: Advocate option adopted, verdict accept) |
| 22 | `agents-run13` | PR #32 | Agents state numbers readably (6.6%, not 0.0659) |
| 23 | `agents-run14` | PR #34 | Custom Base_Portfolio: the investor's own holdings come first |

The persona file in `agents-run6` was the team's version (Kai with `horizon: {min: 20, max: null}`); `agents-run7` applies the one-line fix from PR #22, so from version 16 on, `guide/contract/personas.yaml` in the image matches `main` byte for byte.

How a version was rolled out (from a shell with the account's role, Docker and the AWS CLI):

```bash
IMG=$(aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id guide_runtime-SeZKjzHUQD \
      --query agentRuntimeArtifact.containerConfiguration.containerUri --output text)
REPO=${IMG%:*}
aws ecr get-login-password | docker login --username AWS --password-stdin ${REPO%%/*}
# app/ = guide/, runtime/, config.yaml from main
printf 'FROM %s\nCOPY app/ /app/\n' "$IMG" > Dockerfile
docker build --platform linux/arm64 -t $REPO:agents-runN . && docker push $REPO:agents-runN
# update-agent-runtime needs the full configuration: copy roleArn, networkConfiguration,
# environmentVariables, protocolConfiguration, authorizerConfiguration, etc. from get-agent-runtime,
# and set agentRuntimeArtifact.containerConfiguration.containerUri to the new tag.
aws bedrock-agentcore-control update-agent-runtime --cli-input-json file://rt-update.json
```

To roll back, run the same `update-agent-runtime` with an earlier tag; every tag is still in ECR.

## Session_API Lambda edit (2026-11-15)

The Lambda's `/personas` route returned five personas: its copy of the persona and contract schemas did not allow `risk_level: very_high`, so Kai failed validation. Three edits were made to the deployed package and uploaded with `update-function-code`:

- `guide/contract/personas.schema.json` and `guide/contract/schema.json`: `very_high` added to the `risk_level` enum
- `guide/contract/personas.yaml`: Kai's `horizon: {min: 20, max: null}` became `horizon: {min: 20}`

These are the same edits as PR #22, so `make deploy` from `main` produces the same behaviour. The package before the edit was kept in the workshop IDE at `/tmp/lam/code.zip`.

Second edit (same day): the PR #34 patch (`api/handler.py`, new `guide/contract/base_portfolio.py`) was applied to that package with `git apply` (it applied cleanly, so the rest of the code matched `main`) and uploaded the same way. The package before this edit is `/tmp/lam/before-base.zip`.

## Front end (Amplify)

The Amplify app is not connected to a repository; it is deployed by uploading a zip of `frontend/dist`. Deployment 7 (2026-11-15) is `main` at `939d5c2` (news cards); Deployment 8 adds the PR #34 "Current holdings" field. The zip's `config.json` holds the API URL and the Cognito pool and client IDs from the stack outputs; the committed `frontend/public/config.json` is a blank template on purpose. `scripts/publish_frontend.sh` does the same thing from the stack outputs. The upload used the Amplify API:

```bash
aws amplify create-deployment --app-id d3nprpi8xxns73 --branch-name main   # returns jobId and zipUploadUrl
curl -T frontend.zip "$ZIP_UPLOAD_URL"
aws amplify start-deployment --app-id d3nprpi8xxns73 --branch-name main --job-id $JOB_ID
```

## Guardrail: differs from the code

`infra/stacks/guardrail_stack.py` describes output-only denied topics (RealTransactions, ReturnPredictions) plus the prompt-attack filter. On the live guardrail `3981l0ehd4uu` the two output topics were **removed** on 2026-11-14, because they were blocking legitimate Rulings. Only the prompt-attack filter remains (HIGH on input, CLASSIC tier); it also screens every web snippet through `ApplyGuardrail`. The rules those topics stood for are still enforced in code: the deterministic guidance-only check and the citation validator block transaction language and return predictions, and the news filter drops forecast headlines.

To match the live state in a new account, create the guardrail without the two denied topics. To restore the stricter version, add them back and re-run the 30-session benchmark (`docs/benchmark.md`) to check that Rulings still get through.

## Dataset snapshot

`scripts/add_reference_table.py` created `20261115T154221Z-esg` from `20261113T000000Z-starter`: it copies the manifest, adds the `esg_exclusions` reference table (raw CSV and Parquet, with SHA-256), records which files were carried over, and moves `pointers/current.json`. Re-run it with `--dry-run` first to see what it would write.
