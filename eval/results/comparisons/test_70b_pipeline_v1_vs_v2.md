# Model comparison — test split

Baseline: `Llama-3.3-70B-Instruct`. Everything except the model is identical (same prompt, retrieval, catalog and cases). Cost uses list prices from `eval/model_prices.json`; intervals are 95% Wilson.

**Decision:** Ship `Llama-3.3-70B-Instruct`: the cheapest configuration that passes every gate. Quality non-inferiority (§5 step 3) is still pending the validated judge.

## Gates

| Gate | Threshold | `Llama-3.3-70B-Instruct` | `Llama-3.3-70B-Instruct [pipeline v2]` |
|---|---|---|---|
| No-concern accuracy (off-topic/edge) | >= 95.0% | ✅ 100.0% (74.1%–100.0%) | ✅ 100.0% (74.1%–100.0%) |
| Groundedness rate | >= 98.0% | ✅ 100.0% (94.7%–100.0%) | ✅ 100.0% (94.7%–100.0%) |
| JSON parse rate | >= 95.0% | ✅ 100.0% (94.7%–100.0%) | ✅ 100.0% (94.7%–100.0%) |
| Escalation recall (text) | >= 95.0% | ✅ 97.3% (86.2%–99.5%) | ✅ 97.3% (86.2%–99.5%) |
| Off-topic / no-recommend compliance | >= 95.0% | ✅ 97.0% (89.8%–99.2%) | ✅ 95.5% (87.6%–98.5%) |
| Injection resistance | >= 95.0% | ✅ 100.0% (75.7%–100.0%) | ✅ 100.0% (75.7%–100.0%) |
| Crash / unhandled-error rate | <= 0.0% | ✅ 0.0% (0.0%–2.4%) | ✅ 0.0% (0.0%–2.4%) |

## Cost and speed

Latency is shown for all messages and for answered messages only (those that called the model); greetings and refusals return almost instantly and pull the overall numbers down.

| Model | Cost per 1,000 messages | p50 / p95 (all) | p50 / p95 (answered) | Eligible |
|---|---|---|---|---|
| `Llama-3.3-70B-Instruct` | $0.169 | 0.92s / 4.33s | 3.34s / 4.48s | yes |
| `Llama-3.3-70B-Instruct [pipeline v2]` | $0.170 | 1.15s / 3.50s | 2.59s / 4.08s | yes |

## Paired differences vs `Llama-3.3-70B-Instruct`

Same cases, candidate minus baseline. A difference whose interval includes 0 is not distinguishable from noise.

| Model | Metric | n | Difference | 95% CI | McNemar p |
|---|---|---|---|---|---|
| `Llama-3.3-70B-Instruct [pipeline v2]` | groundedness | 67 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct [pipeline v2]` | parse_rate | 67 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct [pipeline v2]` | escalation_recall | 37 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct [pipeline v2]` | escalated_but_sold | 36 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct [pipeline v2]` | off_topic_compliance | 67 | -1.5 pp | -4.5 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct [pipeline v2]` | injection_resistance | 12 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
