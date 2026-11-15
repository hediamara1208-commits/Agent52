"""A profile without a persona gets the Base_Portfolio of the persona with the closest risk level."""
from guide.contract.personas import SHIPPED_PATH, load_personas
from runtime.app import closest_persona_base

PERSONAS = load_personas(SHIPPED_PATH).personas


def base_of(pid):
    return dict(PERSONAS[pid].contract_values["base_portfolio"].value)


def test_exact_and_nearest_risk_levels():
    assert closest_persona_base("low_to_moderate", PERSONAS) == base_of("robert")
    assert closest_persona_base("moderate", PERSONAS) == base_of("mateo")
    assert closest_persona_base("high", PERSONAS) == base_of("amira")
    assert closest_persona_base("low", PERSONAS) == base_of("robert")


def test_unknown_level_uses_moderate():
    assert closest_persona_base(None, PERSONAS) == base_of("mateo")


def test_extra_personas_never_replace_the_case_bases():
    assert closest_persona_base("very_high", PERSONAS) == base_of("amira")
