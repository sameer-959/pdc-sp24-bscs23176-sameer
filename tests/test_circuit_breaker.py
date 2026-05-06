 

import asyncio
import time
import httpx

BASE = "http://localhost:8000"


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


async def reset():
    async with httpx.AsyncClient() as c:
        await c.post(f"{BASE}/reset-circuit")


async def get_circuit_state() -> str:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/circuit-status")
        return r.json()["state"]


async def ask(label: str):
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BASE}/ask", params={"prompt": "test"})
    elapsed = time.monotonic() - t0
    data = r.json()
    print(
        f"  [{label}] source={data.get('source','?'):<8} "
        f"circuit={data.get('circuit_state','?'):<10} "
        f"time={elapsed:.2f}s  |  "
        f"{data.get('response','')[:60]}"
    )
    return elapsed, data


# ─────────────────────────────────────────────
#  PHASE 1: Naive — no circuit breaker
#  (Simulated: we just show what happens with
#   a direct slow call, timing each attempt)
# ─────────────────────────────────────────────
async def phase1_naive():
    separator("PHASE 1 — NAIVE (No Circuit Breaker)")
    print("  Simulating 3 direct calls to a dead LLM endpoint (5s timeout each).")
    print("  Observe: every single request blocks for the full timeout.\n")

    for i in range(1, 4):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                await c.post("http://localhost:9999/llm", json={"prompt": "test"})
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  Call {i}: FAILED after {elapsed:.2f}s — {type(exc).__name__}")

    print("\n  ⚠  Each blocked request ties up a server thread.")
    print("  With enough users, the server grinds to a halt.\n")


# ─────────────────────────────────────────────
#  PHASE 2: With Circuit Breaker
# ─────────────────────────────────────────────
async def phase2_with_circuit_breaker():
    separator("PHASE 2 — WITH Circuit Breaker")
    await reset()
    print(f"  Circuit reset. State: {await get_circuit_state()}\n")

    # 3 calls — should fail and trip the circuit
    print("  Step A: 3 failing calls (LLM is down) — circuit should OPEN after threshold\n")
    for i in range(1, 4):
        await ask(f"call {i}")

    print(f"\n  Circuit state after failures: {await get_circuit_state()}")

    # Next calls — should be instant fallbacks (OPEN circuit)
    print("\n  Step B: 3 more calls — should be INSTANT fallbacks (fail-fast)\n")
    for i in range(4, 7):
        elapsed, _ = await ask(f"call {i}")
        assert elapsed < 1.0, f"Expected fast fallback, got {elapsed:.2f}s"

    print("\n  ✅ All fallback responses returned in < 1 second — server never blocked!")
    print(f"\n  Circuit state: {await get_circuit_state()}")

    # Wait for recovery timeout, then probe
    recovery = 10
    print(f"\n  Step C: Waiting {recovery}s for recovery timeout → circuit goes HALF_OPEN...")
    await asyncio.sleep(recovery + 1)
    print(f"  Circuit state: {await get_circuit_state()}")

    print("\n  Step D: One probe call (HALF_OPEN allows one attempt)\n")
    await ask("probe")
    print(f"\n  Circuit state after probe: {await get_circuit_state()}")

    separator("SUMMARY")
    print("  • Naive:          Every dead-LLM call blocks for 5s — server paralysed")
    print("  • Circuit Breaker: After 3 failures, all calls get instant fallback")
    print("  • Recovery:        After timeout, circuit probes once and re-evaluates")
    print("  • Server stays responsive to all other users ✅")


async def main():
    # Quick health check
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(BASE)
            r.raise_for_status()
    except Exception:
        print("ERROR: FastAPI server not running. Start it with:")
        print("  uvicorn app.main:app --reload")
        return

    # Check X-Student-ID header
    separator("Checking X-Student-ID Middleware")
    async with httpx.AsyncClient() as c:
        r = await c.get(BASE)
    sid = r.headers.get("x-student-id", "MISSING")
    print(f"  X-Student-ID header: {sid}")
    assert sid == "BSCS23176", f"Expected BSCS23176, got {sid}"
    print("  ✅ Custom header present on every response")

    # Menu for demo options
    print("\nChoose a demo option:")
    print("1. Run without circuit breaker fix (naive approach)")
    print("2. Run with circuit breaker fix")
    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        await phase1_naive()
    elif choice == "2":
        await phase2_with_circuit_breaker()
    else:
        print("Invalid choice. Please enter 1 or 2.")


if __name__ == "__main__":
    asyncio.run(main())