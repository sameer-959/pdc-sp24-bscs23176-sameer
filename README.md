 
Muhammad Sameer | BSCS23176

# PDC-Sp24-BSCS23176-Sameer

**Course:** Parallel and Distributed Computing (PDC)
**Problem Solved:** Problem 3 — Circuit Breaker for LLM Fault Tolerance

---

## Project Structure

```
PDC-Sp24-BSCS23176-Sameer/
├── app/
│   └── main.py          # FastAPI app + Circuit Breaker + Middleware
├── tests/
│   └── test_circuit_breaker.py   # Demo script (before/after)
├── requirements.txt
└── README.md
```

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the server

```bash
uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`

### 3. Run the test/demo script

In a **second terminal**:

```bash
python tests/test_circuit_breaker.py
```

This will:
- Verify the `X-Student-ID: BSCS23176` header on every response
- **Phase 1:** Simulate naive blocking calls (each hangs for 5 seconds)
- **Phase 2:** Show the Circuit Breaker tripping after 3 failures, then serving instant fallbacks

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| POST | `/ask?prompt=...` | Ask LLM (circuit-protected) |
| GET | `/circuit-status` | Inspect circuit breaker state |
| POST | `/reset-circuit` | Reset circuit (for testing) |

---

## Custom Header

Every response includes:
```
X-Student-ID: BSCS23176
```

Implemented via `StudentIDMiddleware` in `app/main.py`.

---

## How the Circuit Breaker Works

```
CLOSED  ──(3 failures)──▶  OPEN  ──(10s timeout)──▶  HALF_OPEN
  ▲                                                        │
  └─────────────(success)─────────────────────────────────┘
```

- **CLOSED:** All requests go to LLM normally
- **OPEN:** Instant fallback returned — server never blocks
- **HALF_OPEN:** One probe request allowed; success resets to CLOSED, failure re-opens"# PDC-Sp24-BSCS23176-Sameer" 
