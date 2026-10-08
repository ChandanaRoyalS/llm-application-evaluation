# Model comparison — dev split

Baseline: `meta-llama/Llama-3.1-8B-Instruct`. Everything except the model is identical (same prompt, retrieval, catalog and cases). Cost uses list prices from `eval/model_prices.json`; intervals are 95% Wilson.

**Decision:** **No configuration ships** (§5 step 5): no candidate passes every gate. Gates failed by every candidate: Escalation recall (text), Off-topic / no-recommend compliance, Injection resistance.

## Gates

| Gate | Threshold | `Llama-3.1-8B-Instruct` | `Llama-3.3-70B-Instruct` | `Qwen3-235B-A22B-Instruct-2507` | `gemma-3-27b-it` |
|---|---|---|---|---|---|
| No-concern accuracy (off-topic/edge) | >= 95.0% | ✅ 100.0% (67.6%–100.0%) | ✅ 100.0% (67.6%–100.0%) | ✅ 100.0% (67.6%–100.0%) | ✅ 100.0% (67.6%–100.0%) |
| Groundedness rate | >= 98.0% | ✅ 98.0% (89.7%–99.7%) | ✅ 100.0% (93.0%–100.0%) | ✅ 98.0% (89.7%–99.7%) | ✅ 98.0% (89.7%–99.7%) |
| JSON parse rate | >= 95.0% | ✅ 98.0% (89.7%–99.7%) | ✅ 100.0% (93.0%–100.0%) | ✅ 100.0% (93.0%–100.0%) | ✅ 100.0% (93.0%–100.0%) |
| Escalation recall (text) | >= 95.0% | ❌ 12.5% (4.3%–31.0%) | ❌ 16.7% (6.7%–35.9%) | ❌ 12.5% (4.3%–31.0%) | ❌ 8.3% (2.3%–25.8%) |
| Off-topic / no-recommend compliance | >= 95.0% | ❌ 86.0% (72.7%–93.4%) | ❌ 88.4% (75.5%–94.9%) | ❌ 90.7% (78.4%–96.3%) | ❌ 86.0% (72.7%–93.4%) |
| Injection resistance | >= 95.0% | ❌ 75.0% (40.9%–92.9%) | ❌ 75.0% (40.9%–92.9%) | ❌ 62.5% (30.6%–86.3%) | ❌ 75.0% (40.9%–92.9%) |
| Crash / unhandled-error rate | <= 0.0% | ✅ 0.0% (0.0%–3.6%) | ✅ 0.0% (0.0%–3.6%) | ✅ 0.0% (0.0%–3.6%) | ✅ 0.0% (0.0%–3.6%) |

## Cost and speed

Latency is shown for all messages and for answered messages only (those that called the model); greetings and refusals return almost instantly and pull the overall numbers down.

| Model | Cost per 1,000 messages | p50 / p95 (all) | p50 / p95 (answered) | Eligible |
|---|---|---|---|---|
| `meta-llama/Llama-3.1-8B-Instruct` | $0.012 | 0.77s / 8.73s | 7.09s / 8.90s | no |
| `meta-llama/Llama-3.3-70B-Instruct` | $0.085 | 0.24s / 3.60s | 2.75s / 3.79s | no |
| `Qwen/Qwen3-235B-A22B-Instruct-2507` | $0.112 | 0.55s / 10.26s | 4.04s / 11.51s | no |
| `google/gemma-3-27b-it` | $0.044 | 0.66s / 14.64s | 11.18s / 16.75s | no |

## Paired differences vs `Llama-3.1-8B-Instruct`

Same cases, candidate minus baseline. A difference whose interval includes 0 is not distinguishable from noise.

| Model | Metric | n | Difference | 95% CI | McNemar p |
|---|---|---|---|---|---|
| `Llama-3.3-70B-Instruct` | groundedness | 51 | +2.0 pp | +0.0 to +5.9 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | parse_rate | 51 | +2.0 pp | +0.0 to +5.9 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | escalation_recall | 24 | +4.2 pp | +0.0 to +12.5 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | escalated_but_sold | 3 | -33.3 pp | -100.0 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | off_topic_compliance | 43 | +2.3 pp | +0.0 to +7.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | injection_resistance | 8 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Qwen3-235B-A22B-Instruct-2507` | groundedness | 51 | +0.0 pp | -5.9 to +5.9 pp | 1.00 |
| `Qwen3-235B-A22B-Instruct-2507` | parse_rate | 51 | +2.0 pp | +0.0 to +5.9 pp | 1.00 |
| `Qwen3-235B-A22B-Instruct-2507` | escalation_recall | 24 | +0.0 pp | -12.5 to +12.5 pp | 1.00 |
| `Qwen3-235B-A22B-Instruct-2507` | escalated_but_sold | 2 | -100.0 pp | -100.0 to -100.0 pp | 0.50 |
| `Qwen3-235B-A22B-Instruct-2507` | off_topic_compliance | 43 | +4.7 pp | +0.0 to +11.6 pp | 0.50 |
| `Qwen3-235B-A22B-Instruct-2507` | injection_resistance | 8 | -12.5 pp | -37.5 to +0.0 pp | 1.00 |
| `gemma-3-27b-it` | groundedness | 51 | +0.0 pp | -5.9 to +5.9 pp | 1.00 |
| `gemma-3-27b-it` | parse_rate | 51 | +2.0 pp | +0.0 to +5.9 pp | 1.00 |
| `gemma-3-27b-it` | escalation_recall | 24 | -4.2 pp | -12.5 to +0.0 pp | 1.00 |
| `gemma-3-27b-it` | escalated_but_sold | 2 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `gemma-3-27b-it` | off_topic_compliance | 43 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `gemma-3-27b-it` | injection_resistance | 8 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
