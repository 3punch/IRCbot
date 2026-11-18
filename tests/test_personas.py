from src.personas import get_persona, list_personas


def test_personas_exist():
    personas = list_personas()
    assert len(personas) >= 5
    ids = [p.id for p in personas]
    assert "general" in ids
    assert "coder" in ids
    assert "creative" in ids
    assert "academic" in ids
    assert "concise" in ids


def test_get_persona_valid():
    coder = get_persona("coder")
    assert coder.id == "coder"
    assert "نرم‌افزار" in coder.name or "کد" in coder.name
    assert len(coder.system_prompt) > 20


def test_get_persona_fallback_to_general():
    unknown = get_persona("unknown_persona_xyz")
    assert unknown.id == "general"
