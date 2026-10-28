# CodeFixer

An AI agent service that repairs broken Python code. Send code and its failing tests; the agent edits the code, re-runs the tests, and repeats until they pass.

## How it works
1. Write the code and tests to a temp folder.
2. Run `pytest` (20s timeout) and capture the error.
3. Send code, tests, and error to an LLM; apply its fix.
4. Repeat up to 5 times. Every run is saved to SQLite.

## Stack
FastAPI, SQLite, OpenAI API, pytest, Docker. Web UI included.

## Run locally
```
pip install -r requirements.txt
copy .env.example .env      # then put your key in .env
py -m uvicorn app:app --reload
```
Open http://127.0.0.1:8000

## API
- `POST /api/fix` body `{"code": "...", "test": "..."}`
- `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/stats`

## Tests
```
py -m pytest tests
```

## Docker
```
docker build -t codefixer .
docker run -p 8000:8000 --env-file .env codefixer
```

## Security note
Fixed code is executed to run the tests. Only run this on your own machine or in a sandbox; do not expose it publicly without isolating execution.

## Results


10 deliberately broken Python files. The agent fixes each, then an **independent**
test suite (not written by the agent) checks whether the fix is really correct.

| file | agent says | really correct |
|------|-----------|----------------|
| add_item | fixed | YES |
| binary_search | fixed | YES |
| count_words | fixed | YES |
| fizzbuzz | fixed | YES |
| flatten | fixed | YES |
| is_valid_password | fixed | **NO** |
| median | fixed | YES |
| second_largest | fixed | YES |
| total_script | failed | YES |
| word_frequency | fixed | YES |

**8–9 of 10 really correct across 4 runs.**

The agent's own tests sometimes pass when the code is still wrong
(`is_valid_password`: both reference implementations produced only all-False
tests, so valid passwords were never checked). This is the limit of
self-testing — which is why the benchmark uses independent tests.
