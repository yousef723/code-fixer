import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient

import app as app_module
import engine

BROKEN = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
TEST = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "test.db")


def test_agent_fixes_broken_code(monkeypatch):
    monkeypatch.setattr(engine, "ask_for_fix", lambda code, test, err: FIXED)
    result = engine.fix_code(BROKEN, TEST)
    assert result["status"] == "fixed"
    assert result["attempts"] == 1
    assert "a + b" in result["final_code"]


def test_agent_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(engine, "ask_for_fix", lambda code, test, err: BROKEN)
    result = engine.fix_code(BROKEN, TEST, max_attempts=3)
    assert result["status"] == "failed"


def test_api_saves_history(monkeypatch):
    monkeypatch.setattr(engine, "ask_for_fix", lambda code, test, err: FIXED)
    client = TestClient(app_module.app)
    res = client.post("/api/fix", json={"code": BROKEN, "test": TEST})
    assert res.status_code == 200
    run_id = res.json()["id"]
    assert client.get("/api/runs").json()[0]["id"] == run_id
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "fixed"
    assert client.get("/api/stats").json()["fixed"] == 1


def test_api_rejects_empty_input():
    client = TestClient(app_module.app)
    assert client.post("/api/fix", json={"code": "", "test": ""}).status_code == 422


def test_agent_writes_tests_when_none_given(monkeypatch):
    monkeypatch.setattr(engine, "generate_tests", lambda code: TEST)
    monkeypatch.setattr(engine, "ask_for_fix", lambda code, test, err: FIXED)
    result = engine.fix_code(BROKEN, "")
    assert result["status"] == "fixed"
    assert result["generated_tests"] is True


def test_api_works_without_tests(monkeypatch):
    monkeypatch.setattr(engine, "generate_tests", lambda code: TEST)
    monkeypatch.setattr(engine, "ask_for_fix", lambda code, test, err: FIXED)
    client = TestClient(app_module.app)
    res = client.post("/api/fix", json={"code": BROKEN})
    assert res.status_code == 200 and res.json()["status"] == "fixed"


def test_generate_tests_endpoint(monkeypatch):
    monkeypatch.setattr(engine, "generate_tests", lambda code: TEST)
    client = TestClient(app_module.app)
    res = client.post("/api/generate-tests", json={"code": BROKEN})
    assert res.status_code == 200 and "def test_add" in res.json()["test"]


def test_generate_tests_retries_on_invalid_output(monkeypatch):
    answers = iter(["def test_a():\n    assert c", TEST, TEST])  # bad first try, good second
    monkeypatch.setattr(engine, "_ask", lambda prompt: next(answers))
    tests = engine.generate_tests(BROKEN)
    assert engine.tests_are_valid(tests)


def test_generate_tests_gives_up_after_tries(monkeypatch):
    monkeypatch.setattr(engine, "_ask", lambda prompt: "def test_a():\n    assert c")
    with pytest.raises(ValueError):
        engine.generate_tests(BROKEN, tries=2)


def _fake_refs(ref_a, ref_b, inputs_a, inputs_b=None):
    """Stand-in for the AI: first call returns reference A, second returns B."""
    answers = iter([
        {"reference": ref_a, "inputs": inputs_a},
        {"reference": ref_b, "inputs": inputs_b or inputs_a},
    ])
    return lambda prompt, temperature: next(answers)


def test_computed_tests_catch_the_bug(monkeypatch):
    ref = "def add(a, b):\n    return a + b\n"
    monkeypatch.setattr(engine, "_ask_json", _fake_refs(ref, ref, [[1, 2], [0, 0], [-1, 1], [5, 7]]))
    tests = engine.generate_tests(BROKEN)
    assert "computed" in tests and engine.tests_are_valid(tests)
    monkeypatch.setattr(engine, "ask_for_fix", lambda code, test, err: FIXED)
    assert engine.fix_code(BROKEN, tests)["status"] == "fixed"


def test_disagreeing_inputs_are_dropped(monkeypatch):
    ref_a = "def add(a, b):\n    return a + b\n"
    ref_b = "def add(a, b):\n    return 0 if a == 1 else a + b\n"
    monkeypatch.setattr(engine, "_ask_json", _fake_refs(ref_a, ref_b, [[0, 0], [2, 2], [3, 1], [1, 2]]))
    tests = engine.generate_tests(BROKEN)
    assert "add(1, 2)" not in tests and "add(2, 2)" in tests


def test_falls_back_when_references_fail(monkeypatch):
    monkeypatch.setattr(engine, "_ask_json", lambda prompt, temperature: (_ for _ in ()).throw(ValueError("x")))
    monkeypatch.setattr(engine, "_ask", lambda prompt, temperature=None: TEST)
    assert engine.generate_tests(BROKEN) == TEST


def test_float_results_use_approx(monkeypatch):
    ref = "def half(x):\n    return x / 2\n"
    monkeypatch.setattr(engine, "_ask_json", _fake_refs(ref, ref, [[1], [3], [5], [0.5]]))
    tests = engine.generate_tests("def half(x):\n    return x\n")
    assert "pytest.approx" in tests


def test_error_cases_use_pytest_raises(monkeypatch):
    ref = "def avg(n):\n    return sum(n) / len(n)\n"
    monkeypatch.setattr(engine, "_ask_json", _fake_refs(ref, ref, [[[]], [[2, 4]], [[1]], [[3, 3]]]))
    tests = engine.generate_tests("def avg(n):\n    return 0\n")
    assert "pytest.raises(ZeroDivisionError)" in tests


def test_api_key_is_not_visible_to_tested_code(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    code = "import os\n\ndef leak():\n    return os.environ.get('OPENAI_API_KEY')\n"
    tests = "from solution import leak\n\ndef test_leak():\n    assert leak() is None\n"
    assert engine.fix_code(code, tests)["status"] == "already_passing"


def test_stops_early_when_ai_makes_no_progress(monkeypatch):
    monkeypatch.setattr(engine, "ask_for_fix", lambda code, test, err: code)
    result = engine.fix_code(BROKEN, TEST, max_attempts=5)
    assert result["status"] == "failed" and len(result["log"]) == 1