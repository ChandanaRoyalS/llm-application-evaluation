# Model comparison — test split

Baseline: `Llama-3.1-8B-Instruct (no triage)`. Everything except the model is identical (same prompt, retrieval, catalog and cases). Cost uses list prices from `eval/model_prices.json`; intervals are 95% Wilson.

**Decision:** **No configuration ships** (§5 step 5): no candidate passes every gate. Gates failed by every candidate: Escalation recall (text), Off-topic / no-recommend compliance.

## Gates

| Gate | Threshold | `Llama-3.1-8B-Instruct (no triage)` | `Llama-3.1-8B-Instruct` |
|---|---|---|---|
| No-concern accuracy (off-topic/edge) | >= 95.0% | ✅ 100.0% (74.1%–100.0%) | ✅ 100.0% (74.1%–100.0%) |
| Groundedness rate | >= 98.0% | ✅ 100.0% (95.4%–100.0%) | ✅ 98.6% (92.5%–99.8%) |
| JSON parse rate | >= 95.0% | ✅ 100.0% (95.4%–100.0%) | ✅ 100.0% (94.9%–100.0%) |
| Escalation recall (text) | >= 95.0% | ❌ 5.4% (1.5%–17.7%) | ❌ 78.4% (62.8%–88.6%) |
| Off-topic / no-recommend compliance | >= 95.0% | ❌ 85.1% (74.7%–91.7%) | ❌ 94.0% (85.6%–97.7%) |
| Injection resistance | >= 95.0% | ✅ 100.0% (75.7%–100.0%) | ✅ 100.0% (75.7%–100.0%) |
| Crash / unhandled-error rate | <= 0.0% | ✅ 0.0% (0.0%–2.4%) | ✅ 0.0% (0.0%–2.4%) |

## Cost and speed

Latency is shown for all messages and for answered messages only (those that called the model); greetings and refusals return almost instantly and pull the overall numbers down.

| Model | Cost per 1,000 messages | p50 / p95 (all) | p50 / p95 (answered) | Eligible |
|---|---|---|---|---|
| `Llama-3.1-8B-Instruct (no triage)` | $0.013 | 3.36s / 9.16s | 5.70s / 11.18s | no |
| `Llama-3.1-8B-Instruct` | $0.025 | 1.45s / 7.47s | 5.57s / 8.51s | no |

## Paired differences vs `Llama-3.1-8B-Instruct (no triage)`

Same cases, candidate minus baseline. A difference whose interval includes 0 is not distinguishable from noise.

| Model | Metric | n | Difference | 95% CI | McNemar p |
|---|---|---|---|---|---|
| `Llama-3.1-8B-Instruct` | groundedness | 72 | -1.4 pp | -4.2 to +0.0 pp | 1.00 |
| `Llama-3.1-8B-Instruct` | parse_rate | 72 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.1-8B-Instruct` | escalation_recall | 37 | +73.0 pp | +59.5 to +86.5 pp | 0.00 |
| `Llama-3.1-8B-Instruct` | escalated_but_sold | 2 | -100.0 pp | -100.0 to -100.0 pp | 0.50 |
| `Llama-3.1-8B-Instruct` | off_topic_compliance | 67 | +9.0 pp | +3.0 to +16.4 pp | 0.03 |
| `Llama-3.1-8B-Instruct` | injection_resistance | 12 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
