"""Run every broken file in benchmark/cases through the agent and print a results table.

The agent writes its own tests. Hidden answer tests in benchmark/truth then check
whether each fix is really correct, so the number is honest.

Usage:  py benchmark.py
"""
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import engine  # noqa: E402

CASES = Path("benchmark/cases")
TRUTH = Path("benchmark/truth")
WORKERS = 3


def really_correct(name, code):
    """Check the final code against my independent answer tests."""
    truth = TRUTH / f"test_{name}.py"
    if not truth.exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "solution.py").write_text(code)
        (work / "test_solution.py").write_text(truth.read_text())
        passed, _ = engine.run_tests(work)
    return passed


def run_case(path):
    name = path.stem
    start = time.time()
    try:
        result = engine.fix_code(path.read_text())
    except Exception as exc:
        return {"name": name, "status": "error", "tests": "-", "attempts": "-",
                "correct": False, "seconds": time.time() - start, "note": str(exc)[:70]}
    computed = "computed by two independent" in result["test_code"]
    return {
        "name": name,
        "status": result["status"],
        "tests": "computed" if computed else "AI-written",
        "attempts": result["attempts"],
        "correct": really_correct(name, result["final_code"]),
        "seconds": time.time() - start,
        "note": "",
    }


def main():
    files = sorted(CASES.glob("*.py"))
    print(f"Running {len(files)} broken files with {engine.MODEL} ...\n")
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(run_case, files))

    lines = [
        "| file | agent says | really correct | tests | fix attempts | seconds |",
        "|------|-----------|----------------|-------|--------------|---------|",
    ]
    for r in rows:
        correct = {True: "YES", False: "NO", None: "n/a"}[r["correct"]]
        lines.append(
            f"| {r['name']} | {r['status']} | {correct} | {r['tests']} | {r['attempts']} | {r['seconds']:.0f} |"
        )
    agent_fixed = sum(r["status"] == "fixed" for r in rows)
    truly = sum(r["correct"] is True for r in rows)
    lines.append("")
    lines.append(f"Agent reported fixed: {agent_fixed} of {len(rows)}")
    lines.append(f"Really correct (independent tests): {truly} of {len(rows)}")
    for r in rows:
        if r["note"]:
            lines.append(f"Error in {r['name']}: {r['note']}")

    report = "\n".join(lines)
    print(report)
    Path("benchmark/results.md").write_text(report + "\n")
    print("\nSaved to benchmark/results.md")


if __name__ == "__main__":
    main()
