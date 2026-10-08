# Model comparison — test split

Baseline: `Llama-3.1-8B-Instruct`. Everything except the model is identical (same prompt, retrieval, catalog and cases). Cost uses list prices from `eval/model_prices.json`; intervals are 95% Wilson.

**Decision:** Ship `Llama-3.3-70B-Instruct`: the cheapest configuration that passes every gate. Quality non-inferiority (§5 step 3) is still pending the validated judge.

## Gates

| Gate | Threshold | `Llama-3.1-8B-Instruct` | `Llama-3.3-70B-Instruct` | `Qwen3-235B-A22B-Instruct-2507` | `gemma-3-27b-it` | `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` |
|---|---|---|---|---|---|---|
| No-concern accuracy (off-topic/edge) | >= 95.0% | ✅ 100.0% (74.1%–100.0%) | ✅ 100.0% (74.1%–100.0%) | ✅ 100.0% (74.1%–100.0%) | ✅ 100.0% (74.1%–100.0%) | ✅ 100.0% (74.1%–100.0%) |
| Groundedness rate | >= 98.0% | ✅ 98.6% (92.5%–99.8%) | ✅ 100.0% (94.7%–100.0%) | ❌ 97.0% (89.8%–99.2%) | ✅ 100.0% (94.8%–100.0%) | ❌ 95.7% (88.1%–98.5%) |
| JSON parse rate | >= 95.0% | ✅ 100.0% (94.9%–100.0%) | ✅ 100.0% (94.7%–100.0%) | ✅ 97.0% (89.8%–99.2%) | ✅ 100.0% (94.8%–100.0%) | ✅ 97.1% (90.2%–99.2%) |
| Escalation recall (text) | >= 95.0% | ❌ 78.4% (62.8%–88.6%) | ✅ 97.3% (86.2%–99.5%) | ✅ 100.0% (90.6%–100.0%) | ✅ 100.0% (90.6%–100.0%) | ✅ 100.0% (90.6%–100.0%) |
| Off-topic / no-recommend compliance | >= 95.0% | ❌ 94.0% (85.6%–97.7%) | ✅ 97.0% (89.8%–99.2%) | ✅ 98.5% (92.0%–99.7%) | ✅ 97.0% (89.8%–99.2%) | ✅ 95.5% (87.6%–98.5%) |
| Injection resistance | >= 95.0% | ✅ 100.0% (75.7%–100.0%) | ✅ 100.0% (75.7%–100.0%) | ✅ 100.0% (75.7%–100.0%) | ❌ 91.7% (64.6%–98.5%) | ✅ 100.0% (75.7%–100.0%) |
| Crash / unhandled-error rate | <= 0.0% | ✅ 0.0% (0.0%–2.4%) | ✅ 0.0% (0.0%–2.4%) | ✅ 0.0% (0.0%–2.4%) | ✅ 0.0% (0.0%–2.4%) | ✅ 0.0% (0.0%–2.4%) |

## Cost and speed

Latency is shown for all messages and for answered messages only (those that called the model); greetings and refusals return almost instantly and pull the overall numbers down.

| Model | Cost per 1,000 messages | p50 / p95 (all) | p50 / p95 (answered) | Eligible |
|---|---|---|---|---|
| `Llama-3.1-8B-Instruct` | $0.025 | 1.45s / 7.47s | 5.57s / 8.51s | no |
| `Llama-3.3-70B-Instruct` | $0.169 | 0.92s / 4.33s | 3.34s / 4.48s | yes |
| `Qwen3-235B-A22B-Instruct-2507` | $0.166 | 1.45s / 14.03s | 6.20s / 16.06s | no |
| `gemma-3-27b-it` | $0.092 | 3.55s / 15.64s | 10.85s / 19.27s | no |
| `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` | $0.104 | 0.99s / 8.96s | 6.61s / 10.40s | no |

## Paired differences vs `Llama-3.1-8B-Instruct`

Same cases, candidate minus baseline. A difference whose interval includes 0 is not distinguishable from noise.

| Model | Metric | n | Difference | 95% CI | McNemar p |
|---|---|---|---|---|---|
| `Llama-3.3-70B-Instruct` | groundedness | 68 | +1.5 pp | +0.0 to +4.4 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | parse_rate | 68 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | escalation_recall | 37 | +18.9 pp | +8.1 to +32.4 pp | 0.02 |
| `Llama-3.3-70B-Instruct` | escalated_but_sold | 29 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.3-70B-Instruct` | off_topic_compliance | 67 | +3.0 pp | +0.0 to +7.5 pp | 0.50 |
| `Llama-3.3-70B-Instruct` | injection_resistance | 12 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Qwen3-235B-A22B-Instruct-2507` | groundedness | 65 | -1.5 pp | -7.7 to +3.1 pp | 1.00 |
| `Qwen3-235B-A22B-Instruct-2507` | parse_rate | 65 | -3.1 pp | -7.7 to +0.0 pp | 0.50 |
| `Qwen3-235B-A22B-Instruct-2507` | escalation_recall | 37 | +21.6 pp | +10.8 to +35.1 pp | 0.01 |
| `Qwen3-235B-A22B-Instruct-2507` | escalated_but_sold | 29 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Qwen3-235B-A22B-Instruct-2507` | off_topic_compliance | 67 | +4.5 pp | -1.5 to +11.9 pp | 0.38 |
| `Qwen3-235B-A22B-Instruct-2507` | injection_resistance | 12 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `gemma-3-27b-it` | groundedness | 68 | +1.5 pp | +0.0 to +4.4 pp | 1.00 |
| `gemma-3-27b-it` | parse_rate | 68 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `gemma-3-27b-it` | escalation_recall | 37 | +21.6 pp | +10.8 to +35.1 pp | 0.01 |
| `gemma-3-27b-it` | escalated_but_sold | 29 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `gemma-3-27b-it` | off_topic_compliance | 67 | +3.0 pp | +0.0 to +7.5 pp | 0.50 |
| `gemma-3-27b-it` | injection_resistance | 12 | -8.3 pp | -25.0 to +0.0 pp | 1.00 |
| `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` | groundedness | 69 | -2.9 pp | -7.2 to +0.0 pp | 0.50 |
| `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` | parse_rate | 69 | -2.9 pp | -7.2 to +0.0 pp | 0.50 |
| `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` | escalation_recall | 37 | +21.6 pp | +10.8 to +35.1 pp | 0.01 |
| `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` | escalated_but_sold | 29 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
| `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` | off_topic_compliance | 67 | +1.5 pp | +0.0 to +4.5 pp | 1.00 |
| `Llama-3.1-8B-Instruct + triage Llama-3.3-70B-Instruct` | injection_resistance | 12 | +0.0 pp | +0.0 to +0.0 pp | 1.00 |
