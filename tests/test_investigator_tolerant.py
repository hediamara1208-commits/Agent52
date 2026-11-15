"""Live failure (session 118de85a…): a Hard_Rule-based risk with `exhibits: []` sank the whole
Investigator. Now that risk is kept, and only a malformed risk is dropped on its own."""
import json

from guide.agents.investigator import check_findings, parse_output


class _Reg:
    def get(self, n):
        return object() if n == 1 else None


CONTRACT = {"risk_level": "low", "per_asset_cap": 0.1}

RAW = "```json " + json.dumps({"per_option": [{"option_id": "request", "material_risks": [
    {"risk": "Single-position concentration", "exhibits": [],
     "why_for_this_person": "0.3 vs per-asset limit 0.1", "contract_fields": ["per_asset_cap"]},
    {"risk": "Volatility", "exhibits": [1], "why_for_this_person": "high vol",
     "contract_fields": ["risk_level"], "extra": "ignored"},
    {"risk": "broken"},
]}]}) + " ```"


def test_rule_based_risk_without_exhibit_is_kept_and_malformed_one_dropped():
    data = parse_output(RAW)
    res = check_findings(data, CONTRACT, _Reg(), ["request"])
    kept = res.per_option[0]["material_risks"]
    assert [r["risk"] for r in kept] == ["Single-position concentration", "Volatility"]
    assert "extra" not in kept[1]
    assert [r.risk for r in res.rejected] == ["broken"]
