 


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import httpx
import asyncio
import time
import enum
from typing import Optional

# ─────────────────────────────────────────────
#  Custom Middleware: X-Student-ID header
# ─────────────────────────────────────────────
class StudentIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Student-ID"] = "BSCS23176"
        return response


# ─────────────────────────────────────────────
#  Circuit Breaker Implementation
# ─────────────────────────────────────────────
class CircuitState(enum.Enum):
    CLOSED   = "CLOSED"    # Normal — requests flow through
    OPEN     = "OPEN"      # Tripped — requests fail fast
    HALF_OPEN = "HALF_OPEN" # Testing — one probe request allowed


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 10.0,
        name: str = "default"
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        # Auto-transition OPEN → HALF_OPEN after recovery timeout
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time is not None
            and (time.monotonic() - self._last_failure_time) >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        s = self.state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.HALF_OPEN:
            return True   # allow exactly one probe
        return False      # OPEN — fail fast

    def status(self) -> dict:
        return {
            "circuit": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout,
        }


# Singleton circuit breaker for the LLM service
llm_circuit = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=10.0,
    name="llm-api"
)

# Simulated LLM endpoint (overridable in tests)
LLM_API_URL = "http://localhost:9999/llm"  # intentionally unreachable for demo


# ─────────────────────────────────────────────
#  FastAPI App
# ─────────────────────────────────────────────
app = FastAPI(title="StudySync API", version="1.0.0")

app.add_middleware(StudentIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
#  LLM call helper
# ─────────────────────────────────────────────
async def call_llm(prompt: str, timeout: float = 5.0) -> str:
    """
    Calls the external LLM API.
    Raises httpx.TimeoutException or httpx.HTTPError on failure.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LLM_API_URL,
            json={"prompt": prompt},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("text", "")


# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "StudySync API is running", "student_id": "BSCS23176"}


@app.get("/circuit-status")
async def circuit_status():
    """Inspect the LLM circuit breaker state."""
    return llm_circuit.status()


@app.post("/ask")
async def ask_llm(prompt: str = "Explain recursion"):
    """
    Protected LLM endpoint.
    - If circuit is CLOSED/HALF_OPEN: attempt real call
    - If circuit is OPEN: return fallback immediately (fail-fast)
    - On call failure: record failure, possibly trip circuit, return fallback
    """
    # ── Fail-fast path ──────────────────────────────────────────────────────
    if not llm_circuit.allow_request():
        return {
            "source": "fallback",
            "circuit_state": llm_circuit.state.value,
            "response": (
                "Our AI tutor is temporarily unavailable. "
                "Please try again in a few seconds, or browse your saved notes."
            ),
        }

    # ── Attempt real call ───────────────────────────────────────────────────
    try:
        text = await call_llm(prompt)
        llm_circuit.record_success()
        return {
            "source": "llm",
            "circuit_state": llm_circuit.state.value,
            "response": text,
        }

    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
        llm_circuit.record_failure()
        return {
            "source": "fallback",
            "circuit_state": llm_circuit.state.value,
            "failure_count": llm_circuit._failure_count,
            "response": (
                "Our AI tutor is temporarily unavailable. "
                "Please try again in a few seconds, or browse your saved notes."
            ),
            "error": str(exc),
        }


@app.post("/reset-circuit")
async def reset_circuit():
    """Manually reset the circuit breaker (for testing)."""
    llm_circuit._state = CircuitState.CLOSED
    llm_circuit._failure_count = 0
    llm_circuit._last_failure_time = None
    return {"message": "Circuit reset", **llm_circuit.status()}