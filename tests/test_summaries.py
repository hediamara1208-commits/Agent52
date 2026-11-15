from datetime import date

from hypothesis import given, strategies as st

from guide.toolkit.exhibits import ExhibitRegistry
from guide.tribunal.summaries import build_summaries, build_summary, figure, summarize, word_count


def _registry():
    reg = ExhibitRegistry()
    reg.add(metric="annualized_volatility", value=0.201, period_start=date(2021, 11, 12),
            period_end=date(2026, 11, 12), assets=("TSLA",), currency="CAD",
            source_files=("prices@s",), processing_notes=(), inputs={})
    return reg


def test_short_text_unchanged():
    assert summarize("One. Two.") == "One. Two."


def test_truncates_at_sentence_boundary():
    text = " ".join(["Sentence one has five words."] + ["word"] * 70 + ["end."])
    out = summarize(text)
    assert out == "Sentence one has five words."


def test_long_single_sentence_cut_without_breaking_link():
    text = " ".join(["w"] * 59) + " [Exhibit 12] more words follow here"
    out = summarize(text)
    assert word_count(out) <= 60
    assert "[Exhibit" not in out
    assert out.endswith(".")


@given(st.lists(st.text(alphabet="abc .!?[]", min_size=1, max_size=12), max_size=200))
def test_never_exceeds_limit(words):
    assert word_count(summarize(" ".join(words))) <= 60


def test_figure_from_exhibit_and_missing():
    reg = _registry()
    assert figure(reg, 1, kind="pct") == "20.1% [Exhibit 1]"
    assert figure(reg, 99) is None


def test_judge_summary_has_exhibit_link_and_limit():
    reg = _registry()
    out = {"verdict": "accept_with_conditions", "failing_rules": ["per_asset_cap"],
           "conditions": ["cap at 10%"],
           "figures": [{"exhibit": 1, "label": "Volatility", "kind": "pct"},
                       {"exhibit": 42, "label": "Ghost"}]}
    s = build_summary("judge", out, reg)
    assert "accept with conditions" in s and "[Exhibit 1]" in s and "Ghost" not in s
    assert word_count(s) <= 60


def test_build_summaries_per_stage():
    reg = _registry()
    res = build_summaries({"advocate": {"goal": "grow savings", "options": [{}, {"rejected": True}]},
                           "investigator": {"risks": [{"option": "A"}, {"option": "B"}]}}, reg)
    assert set(res) == {"advocate", "investigator"}
    assert "2 options" in res["advocate"]
