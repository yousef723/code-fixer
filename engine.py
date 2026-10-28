"""The agent loop: write tests -> run them -> read errors -> ask AI to fix -> repeat.

Tests are built by differential testing: two independent AI-written reference
implementations are run in a sandbox, and only the inputs where both agree become
test cases. Expected values are computed by Python, never guessed by the AI.
"""
import ast
import builtins
import json
import math
import numbers
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from openai import OpenAI

MODEL = os.getenv("MODEL", "gpt-4o-mini")
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
TEST_TIMEOUT = 20       # seconds for a test run (stops infinite loops)
REFERENCE_TIMEOUT = 10  # seconds for running a reference implementation
MIN_CASES = 3           # minimum agreed test cases per function
MIN_OK_CASES = 2        # at least this many must check a real returned value
MAX_FUNCTIONS = 3
RAISES = {"ValueError", "TypeError", "ZeroDivisionError", "IndexError", "KeyError"}

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(timeout=60, max_retries=2)  # reads OPENAI_API_KEY from environment
    return _client


# ---------- helpers ----------

def _safe_env():
    """Environment for running untrusted code: no API keys, no secrets."""
    env = {
        k: v for k, v in os.environ.items()
        if not any(word in k.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # avoid stale .pyc
    return env


def _clean(text):
    """Pull code out of an AI reply, with or without markdown fences."""
    text = text.strip()
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    if match:
        return match.group(1).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    return text.strip()


def _parses(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _ask(prompt, temperature=None):
    """Call the AI for text. Raises ValueError if the reply was cut off."""
    kwargs = {"temperature": temperature} if temperature is not None else {}
    reply = get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    if reply.choices[0].finish_reason == "length":
        raise ValueError("AI reply was cut off")
    return _clean(reply.choices[0].message.content)


def _ask_json(prompt, temperature):
    """Call the AI for a JSON object. Raises ValueError if cut off or invalid."""
    reply = get_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    if reply.choices[0].finish_reason == "length":
        raise ValueError("AI reply was cut off")
    try:
        data = json.loads(reply.choices[0].message.content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI returned invalid JSON: {exc}")
    if not isinstance(data, dict):
        raise ValueError("AI returned JSON that is not an object")
    return data


# ---------- running tests ----------

def run_tests(workdir):
    """Run pytest in workdir. Returns (passed, output)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "test_solution.py", "-q", "--tb=short", "-p", "no:cacheprovider"],
            capture_output=True,
            text=True,
            cwd=workdir,
            timeout=TEST_TIMEOUT,
            env=_safe_env(),
        )
    except subprocess.TimeoutExpired:
        return False, f"Tests timed out after {TEST_TIMEOUT}s (possible infinite loop)."
    return result.returncode == 0, result.stdout + result.stderr


# ---------- fixing code ----------

def ask_for_fix(code, test_code, error):
    """Ask the AI for a corrected version of the code."""
    prompt = (
        "This Python file fails its tests. Fix the CODE so the tests pass.\n"
        "Rules: do not change the tests. Keep function names and signatures unchanged. "
        "Fix the real logic; never hardcode or special-case the test inputs.\n\n"
        f"CODE (solution.py):\n{code}\n\n"
        f"TESTS (test_solution.py):\n{test_code}\n\n"
        f"TEST OUTPUT:\n{error}\n\n"
        "Return ONLY the full corrected solution.py. No explanation, no markdown."
    )
    return _ask(prompt)


# ---------- writing tests (differential testing) ----------

_RUNNER = """
import inspect, json, sys
payload = json.load(sys.stdin)
ns = {}
exec(payload["ref"], ns)
f = ns[payload["name"]]
out = []
for args in payload["inputs"]:
    try:
        inspect.signature(f).bind(*args)
    except TypeError:
        out.append({"skip": True})  # wrong number of arguments: not a real test case
        continue
    try:
        r = repr(f(*args))
        out.append({"ok": r} if len(r) <= 300 else {"skip": True})
    except Exception as e:
        out.append({"err": type(e).__name__})
print(json.dumps(out))
"""


def _reference(code, name, temperature):
    """Ask the AI for a correct reference implementation plus test inputs."""
    prompt = (
        f"Here is Python code that may contain bugs:\n\n{code}\n\n"
        f"Write a CORRECT reference implementation of the function `{name}`, behaving as the code is "
        "clearly meant to behave. Use only the standard library. It must be self-contained: "
        "redefine any helper functions it needs. Then list 8 test inputs for it, including edge cases "
        "(empty, zero, negative, single item). Each input is the list of the function's arguments, one per parameter. "
        "Include mostly normal valid inputs, and include cases where the answer is different (for example both "
        "valid and invalid inputs). Examples: a function with one list parameter gets [[1, 2, 3]]; "
        "a function with one string parameter gets ['abc']; a function with two numbers gets [4, 5]. "
        "Never wrap a string or number in an extra list.\n"
        'Return ONLY JSON like: {"reference": "def name(...):\\n    ...", "inputs": [[1, 2], [0, 0]]}'
    )
    data = _ask_json(prompt, temperature)
    ref, inputs = data.get("reference"), data.get("inputs")
    if not isinstance(ref, str) or not _parses(ref):
        raise ValueError("Bad reference implementation")
    if not isinstance(inputs, list) or not all(isinstance(i, list) for i in inputs):
        raise ValueError("Bad test inputs")
    return ref, inputs


def _run_reference(ref, name, inputs):
    """Run a reference implementation on the inputs in a sandboxed subprocess."""
    proc = subprocess.run(
        [sys.executable, "-c", _RUNNER],
        input=json.dumps({"ref": ref, "name": name, "inputs": inputs}),
        capture_output=True,
        text=True,
        timeout=REFERENCE_TIMEOUT,
        env=_safe_env(),
    )
    if proc.returncode != 0:
        raise ValueError("Reference implementation crashed")
    return json.loads(proc.stdout)


def _same(a, b):
    """Compare two results; numbers are compared with a tolerance."""
    if isinstance(a, numbers.Number) and isinstance(b, numbers.Number) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, (list, tuple)) and type(a) is type(b):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _agreed_cases(code, name):
    """Return test cases on which two independent reference implementations agree."""
    ref1, inputs1 = _reference(code, name, 0.2)
    ref2, inputs2 = _reference(code, name, 0.9)
    inputs, seen = [], set()
    for args in inputs1 + inputs2:
        key = json.dumps(args, sort_keys=True)
        if key not in seen:
            seen.add(key)
            inputs.append(args)
    inputs = inputs[:12]
    out1, out2 = _run_reference(ref1, name, inputs), _run_reference(ref2, name, inputs)

    cases = []
    for args, a, b in zip(inputs, out1, out2):
        if "ok" in a and "ok" in b:
            try:
                va, vb = ast.literal_eval(a["ok"]), ast.literal_eval(b["ok"])
            except (ValueError, SyntaxError):
                continue
            if _same(va, vb):
                cases.append(("ok", args, a["ok"], va))
        elif "err" in a and "err" in b and a["err"] == b["err"] and a["err"] in RAISES:
            cases.append(("err", args, a["err"], None))
    return cases


def _has_float(value):
    if isinstance(value, float):
        return True
    return isinstance(value, (list, tuple)) and any(_has_float(v) for v in value)


def _differential_tests(code):
    """Build a pytest file whose expected values were computed, not guessed."""
    names = re.findall(r"^def\s+([A-Za-z]\w*)\s*\(", code, re.M)[:MAX_FUNCTIONS]
    if not names:
        raise ValueError("No functions to test")
    lines = [
        "# Expected values computed by two independent reference implementations that agreed.",
        "import pytest",
        f"from solution import {', '.join(names)}",
        "",
    ]
    for name in names:
        cases = _agreed_cases(code, name)
        ok_results = [c[2] for c in cases if c[0] == "ok"]
        if len(cases) < MIN_CASES or len(ok_results) < MIN_OK_CASES or len(set(ok_results)) < 2:
            # too few cases, or every expected value is identical (e.g. all False): tests too weak
            raise ValueError(f"Not enough varied real-answer cases for {name}")
        for i, (kind, args, expected, value) in enumerate(cases, 1):
            call = f"{name}({', '.join(repr(x) for x in args)})"
            lines.append(f"def test_{name}_{i}():")
            if kind == "err":
                lines += [f"    with pytest.raises({expected}):", f"        {call}"]
            elif isinstance(value, (float, list, tuple)) and _has_float(value):
                lines.append(f"    assert {call} == pytest.approx({expected})")
            else:
                lines.append(f"    assert {call} == {expected}")
            lines.append("")
    return "\n".join(lines)


def tests_are_valid(test_code):
    """True if the tests are complete Python, contain a test, and use no undefined names."""
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return False
    if "def test_" not in test_code:
        return False
    defined = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            defined.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            defined.update(a.asname or a.name for a in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            defined.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return used <= defined


def generate_tests(code, tries=3):
    """Write tests. Prefer computed (differential) tests; fall back to AI-written ones."""
    try:
        tests = _differential_tests(code)
        if tests_are_valid(tests):
            return tests
    except Exception:
        pass  # scripts without functions, disagreeing references, API hiccups: use the fallback

    for _ in range(tries):
        try:
            tests = review_tests(code, _generate_once(code))
        except ValueError:
            continue
        if tests_are_valid(tests):
            return tests
    raise ValueError("The AI could not write valid tests. Try again.")


def _generate_once(code):
    """Fallback: ask the AI to write pytest tests for what the code is clearly meant to do."""
    prompt = (
        "Write pytest tests for the intended behavior of this Python code. "
        "The code may contain bugs; test what it is clearly meant to do, not what it does now.\n"
        "Rules: the code is saved as solution.py and the tests as test_solution.py. "
        "If it defines functions, import them with `from solution import ...`. "
        "If it is a plain script with no functions, use "
        "`import runpy` and `runpy.run_path('solution.py')` with the `capsys` fixture to check printed output. "
        "Never copy the code's current output: if the code has a bug, the tests must FAIL on it. "
        "For any expected value that needs counting or math, write it as a Python expression using the "
        "standard library (for example math.factorial(3)), never as a number you worked out yourself. "
        "Use short, obvious inputs. Use pytest.approx for floats. "
        "Keep it to a few simple asserts.\n\n"
        f"CODE:\n{code}\n\n"
        "Return ONLY the test file code. No explanation, no markdown."
    )
    return _ask(prompt)


def review_tests(code, tests):
    """Second pass: the AI checks its own tests and corrects any that copy a bug."""
    prompt = (
        "Review these pytest tests for the code below. The code may contain bugs. "
        "Each expected value must be the CORRECT answer for what the code is meant to do, "
        "not what the buggy code currently returns. Fix any wrong expected value. "
        "Replace any hand-computed number with a standard-library expression where one exists. "
        "Remove comments that mention bugs or assumptions. Keep the same imports and style.\n\n"
        f"CODE:\n{code}\n\nTESTS:\n{tests}\n\n"
        "Return ONLY the corrected test file code. No explanation, no markdown."
    )
    return _ask(prompt)


# ---------- the agent loop ----------

def fix_code(code, test_code="", max_attempts=MAX_ATTEMPTS):
    """Run the agent loop. Returns a dict with status, attempts, final code, log."""
    generated = not test_code.strip()
    if generated:
        test_code = generate_tests(code)
    log = []
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        (workdir / "test_solution.py").write_text(test_code)
        current = code

        for attempt in range(1, max_attempts + 1):
            (workdir / "solution.py").write_text(current)
            passed, output = run_tests(workdir)
            log.append({"attempt": attempt, "passed": passed, "output": output[-1500:]})
            if passed:
                return {
                    "status": "fixed" if attempt > 1 else "already_passing",
                    "attempts": attempt - 1,
                    "final_code": current,
                    "log": log,
                    "test_code": test_code,
                    "generated_tests": generated,
                }
            if attempt == max_attempts:
                break
            try:
                new = ask_for_fix(current, test_code, output[-4000:])
            except ValueError:  # reply cut off: try again next round
                continue
            if not _parses(new):  # reply is not valid Python: try again next round
                continue
            if new.strip() == current.strip():  # no progress: stop early
                break
            current = new

    return {"status": "failed", "attempts": max_attempts - 1, "final_code": current, "log": log,
            "test_code": test_code, "generated_tests": generated}