# Run-to-run variation — test split

Each configuration: one run at temperature 0 plus repeats at the provider's default temperature. A difference between configurations smaller than the spread here is a tie.

## Llama-3.1-8B-Instruct (1 runs)

| Gate | t0 | mean | min–max |
|---|---|---|---|
| No-concern accuracy (off-topic/edge) | 100.0% | 100.0% | 100.0–100.0% |
| Groundedness rate | 98.6% | 98.6% | 98.6–98.6% |
| JSON parse rate | 100.0% | 100.0% | 100.0–100.0% |
| Escalation recall (text) | 78.4% | 78.4% | 78.4–78.4% |
| Off-topic / no-recommend compliance | 94.0% | 94.0% | 94.0–94.0% |
| Injection resistance | 100.0% | 100.0% | 100.0–100.0% |
| Crash / unhandled-error rate | 0.0% | 0.0% | 0.0–0.0% |

## Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct (1 runs)

| Gate | t0 | mean | min–max |
|---|---|---|---|
| No-concern accuracy (off-topic/edge) | 100.0% | 100.0% | 100.0–100.0% |
| Groundedness rate | 95.7% | 95.7% | 95.7–95.7% |
| JSON parse rate | 97.1% | 97.1% | 97.1–97.1% |
| Escalation recall (text) | 100.0% | 100.0% | 100.0–100.0% |
| Off-topic / no-recommend compliance | 95.5% | 95.5% | 95.5–95.5% |
| Injection resistance | 100.0% | 100.0% | 100.0–100.0% |
| Crash / unhandled-error rate | 0.0% | 0.0% | 0.0–0.0% |

## Llama-3.3-70B-Instruct (4 runs)

| Gate | t0 | default r1 | default r2 | default r3 | mean | min–max |
|---|---|---|---|---|---|---|
| No-concern accuracy (off-topic/edge) | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0–100.0% |
| Groundedness rate | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0–100.0% |
| JSON parse rate | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0–100.0% |
| Escalation recall (text) | 97.3% | 97.3% | 97.3% | 97.3% | 97.3% | 97.3–97.3% |
| Off-topic / no-recommend compliance | 97.0% | 97.0% | 97.0% | 97.0% | 97.0% | 97.0–97.0% |
| Injection resistance | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0–100.0% |
| Crash / unhandled-error rate | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0–0.0% |

## Qwen3-235B-A22B-Instruct-2507 (1 runs)

| Gate | t0 | mean | min–max |
|---|---|---|---|
| No-concern accuracy (off-topic/edge) | 100.0% | 100.0% | 100.0–100.0% |
| Groundedness rate | 97.0% | 97.0% | 97.0–97.0% |
| JSON parse rate | 97.0% | 97.0% | 97.0–97.0% |
| Escalation recall (text) | 100.0% | 100.0% | 100.0–100.0% |
| Off-topic / no-recommend compliance | 98.5% | 98.5% | 98.5–98.5% |
| Injection resistance | 100.0% | 100.0% | 100.0–100.0% |
| Crash / unhandled-error rate | 0.0% | 0.0% | 0.0–0.0% |

## gemma-3-27b-it (1 runs)

| Gate | t0 | mean | min–max |
|---|---|---|---|
| No-concern accuracy (off-topic/edge) | 100.0% | 100.0% | 100.0–100.0% |
| Groundedness rate | 100.0% | 100.0% | 100.0–100.0% |
| JSON parse rate | 100.0% | 100.0% | 100.0–100.0% |
| Escalation recall (text) | 100.0% | 100.0% | 100.0–100.0% |
| Off-topic / no-recommend compliance | 97.0% | 97.0% | 97.0–97.0% |
| Injection resistance | 91.7% | 91.7% | 91.7–91.7% |
| Crash / unhandled-error rate | 0.0% | 0.0% | 0.0–0.0% |
