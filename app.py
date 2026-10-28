"""Backend: FastAPI + SQLite run history."""
import json
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

load_dotenv()

import engine  # noqa: E402  (after load_dotenv so env vars are set)

DB_PATH = Path("runs.db")
app = FastAPI(title="CodeFixer")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT, attempts INTEGER,
            original_code TEXT, test_code TEXT, final_code TEXT, log TEXT)"""
    )
    return conn


class FixRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    test: str = Field(default="", max_length=20000)


@app.post("/api/fix")
def fix(req: FixRequest):
    try:
        result = engine.fix_code(req.code, req.test)
    except Exception as exc:  # e.g. missing API key, network error
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO runs (status, attempts, original_code, test_code, final_code, log)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (result["status"], result["attempts"], req.code, result["test_code"],
             result["final_code"], json.dumps(result["log"])),
        )
        result["id"] = cur.lastrowid
    return result


class TestsRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)


@app.post("/api/generate-tests")
def generate_tests(req: TestsRequest):
    try:
        return {"test": engine.generate_tests(req.code)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}")


@app.get("/api/runs")
def list_runs():
    with db() as conn:
        rows = conn.execute(
            "SELECT id, created_at, status, attempts FROM runs ORDER BY id DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/runs/{run_id}")
def get_run(run_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    data = dict(row)
    data["log"] = json.loads(data["log"])
    return data


@app.get("/api/stats")
def stats():
    with db() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM runs GROUP BY status").fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    total = sum(counts.values())
    fixed = counts.get("fixed", 0)
    failed = counts.get("failed", 0)
    attempted = fixed + failed
    return {
        "total_runs": total,
        "fixed": fixed,
        "failed": failed,
        "fix_rate": round(fixed / attempted * 100, 1) if attempted else None,
    }


@app.get("/")
def home():
    return FileResponse("static/index.html")
