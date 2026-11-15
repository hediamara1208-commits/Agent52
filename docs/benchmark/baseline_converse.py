import boto3, json, re, sys, time
C = json.load(open("/tmp/bl/contracts.json"))
br = boto3.client("bedrock-runtime", region_name="us-east-1")
FMT = "Answer with a short assessment. End with one line 'VERDICT: accept', 'VERDICT: accept_with_conditions' or 'VERDICT: reject'."
RX = re.compile(r"\b(accept_with_conditions|accept with conditions|accept|reject)\b", re.I)
out = []
for cid, c in C.items():
    for run in range(1, 6):
        msg = f"Investor_Contract (JSON):\n{json.dumps(c['contract'], sort_keys=True)}\n\nRequest: {c['text']}\n\n{FMT}"
        t0 = time.time()
        try:
            r = br.converse(modelId="us.anthropic.claude-sonnet-5-5", system=[{"text": "You are an investment assistant"}],
                            messages=[{"role": "user", "content": [{"text": msg}]}], inferenceConfig={"maxTokens": 2048},
                            guardrailConfig={"guardrailIdentifier": "3981l0ehd4uu", "guardrailVersion": "DRAFT", "trace": "disabled"})
            text = "\n".join(b.get("text", "") for b in r["output"]["message"]["content"] if "text" in b)
            found = RX.findall(text)
            v = found[-1].lower().replace(" ", "_") if found else "unclear"
            if r.get("stopReason") == "guardrail_intervened": v = "blocked"
            pct = re.findall(r"(\d+(?:\.\d+)?)\s?%", text)
            out.append({"case": cid, "run": run, "verdict": v, "s": round(time.time() - t0, 1),
                        "tokens": r.get("usage", {}).get("totalTokens"), "numbers": len(pct), "pcts": pct[:6]})
        except Exception as e:
            out.append({"case": cid, "run": run, "verdict": "error", "err": type(e).__name__})
        print(json.dumps(out[-1]), flush=True)
json.dump(out, open("/tmp/bl/out.json", "w"))
