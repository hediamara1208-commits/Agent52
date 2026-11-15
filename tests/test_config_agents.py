import pytest

from guide.config import Config, load_config

BASE = {"s3_bucket": "b"}


def test_model_ids_fall_back_to_model_id():
    cfg = Config(**BASE, model_id="m", model_ids={"judge": "j", "advocate": ""})
    assert cfg.model_ids == {"advocate": "m", "investigator": "m", "judge": "j"}


def test_invalid_scope_rejected():
    with pytest.raises(ValueError):
        Config(**BASE, advocate_scope="all")


@pytest.mark.parametrize("value", [0, -1, True])
def test_timeout_must_be_positive(value):
    with pytest.raises(ValueError):
        Config(**BASE, agent_timeout_seconds=value)


def test_unknown_agent_rejected():
    with pytest.raises(ValueError):
        Config(**BASE, model_ids={"clerk": "x"})


def test_shipped_config_and_env_override():
    cfg = load_config(env={})
    assert cfg.advocate_scope == "size_only" and cfg.agent_timeout_seconds == 60
    assert all(cfg.model_ids.values())
    cfg = load_config(env={"GUIDE_ADVOCATE_SCOPE": "universe", "GUIDE_AGENT_TIMEOUT_SECONDS": "30"})
    assert cfg.advocate_scope == "universe" and cfg.agent_timeout_seconds == 30.0
