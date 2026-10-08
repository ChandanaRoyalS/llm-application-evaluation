# Model comparison — dev split

Baseline: `meta-llama/Llama-3.1-8B-Instruct`. Everything except the model is identical (same prompt, retrieval, catalog and cases). Cost uses list prices from `eval/model_prices.json`; intervals are 95% Wilson.

**Decision:** **No configuration ships** (§5 step 5): no candidate passes every gate. Gates failed by every candidate: Escalation recall (text), Injection resistance.

## Gates

| Gate | Threshold | `Llama-3.1-8B-Instruct` | `Llama-3.1-8B-Instruct` |
|---|---|---|---|
| No-concern accuracy (off-topic/edge) | >= 95.0% | ✅ 100.0% (67.6%–100.0%) | ✅ 100.0% (67.6%–100.0%) |
| Groundedness rate | >= 98.0% | ✅ 98.0% (89.7%–99.7%) | ✅ 100.0% (92.4%–100.0%) |
| JSON parse rate | >= 95.0% | ✅ 98.0% (89.7%–99.7%) | ✅ 100.0% (92.4%–100.0%) |
| Escalation recall (text) | >= 95.0% | ❌ 12.5% (4.3%–31.0%) | ❌ 79.2% (59.5%–90.8%) |
| Off-topic / no-recommend compliance | >= 95.0% | ❌ 86.0% (72.7%–93.4%) | ✅ 95.3% (84.5%–98.7%) |
| Injection resistance | >= 95.0% | ❌ 75.0% (40.9%–92.9%) | ❌ 75.0% (40.9%–92.9%) |
| Crash / unhandled-error rate | <= 0.0% | ✅ 0.0% (0.0%–3.6%) | ✅ 0.0% (0.0%–3.6%) |

## Cost and speed

Latency is shown for all messages and for answered messages only (those that called the model); greetings and refusals return almost instantly and pull the overall numbers down.

| Model | Cost per 1,000 messages | p50 / p95 (all) | p50 / p95 (answered) | Eligible |
|---|---|---|---|---|
| `meta-llama/Llama-3.1-8B-Instruct` | $0.012 | 0.77s / 8.73s | 7.09s / 8.90s | no |
| `meta-llama/Llama-3.1-8B-Instruct` | $0.021 | 2.05s / 8.58s | 6.65s / 12.82s | no |

## Paired differences vs `Llama-3.1-8B-Instruct`

Same cases, candidate minus baseline. A difference whose interval includes 0 is not distinguishable from noise.

| Model | Metric | n | Difference | 95% CI | McNemar p |
|---|---|---|---|---|---|
| `Llama-3.1-8B-Instruct` | groundedness | 47 | +2.1 pp | +0.0 to +6.4 pp | 1.00 |
| `Llama-3.1-8B-Instruct` | parse_rate | 47 | +2.1 pp | +0.0 to +6.4 pp | 1.00 |
| `Llama-3.1-8B-Instruct` | escalation_recall | 24 | +66.7 pp | +45.8 to +83.3 pp | 0.00 |
| `Llama-3.1-8B-Instruct` | escalated_but_sold | 3 | -100.0 pp | -100.0 to -100.0 pp | 0.25 |
| `Llama-3.1-8B-Instruct` | off_topic_compliance | 43 | +9.3 pp | +2.3 to +18.6 pp | 0.12 |
| `Llama-3.1-8B-Instruct` | injection_resistance | 8 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
