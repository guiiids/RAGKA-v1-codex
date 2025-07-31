# Hybrid Intent Routing: Current State & Next Steps

## Current Feature State

- Hybrid fallback logic implemented in `GPT4IntentClassifier.classify_query`:
  - GPT-4 intent classification as primary source.
  - If GPT confidence < 0.5 **and** `self.fallback_classifier` is present:
    1. Invoke the regex-based `EnhancedPatternMatcher.classify_query(query, history)`.
    2. If regex returns `CONTEXTUAL_FOLLOW_UP`, immediately use that intent.
    3. Otherwise, compare regex confidence vs. GPT confidence and pick the higher score.
- New ML threshold of **0.5** for handoff to regex on follow-up scenarios.
- Updated unit tests to cover hybrid behavior (low GPT confidence + regex follow-up).
- EnhancedPatterns library confirmed to include strong indicators (`what next`, `then`, `continue`) for follow-up detection.

## Recommended Next Steps

1. **Extend Training Data**
   - Ingest a sample set (e.g., 1K queries) from production logs.
   - Label and integrate these real examples into the synthetic training generator.
   - Add adversarial/ambiguous cases to strengthen boundary detection.

2. **Augment Regex Patterns**
   - Review ENHANCED_PATTERNS for `CONTEXTUAL_FOLLOW_UP`:
     - Ensure coverage of “then what”, “what’s next?”, “after that”, “more details”.
   - Add any missing strong indicators to enhance fallback accuracy.

3. **Observability & Monitoring**
   - Instrument telemetry to track:
     - Per-intent inference latency (GPT vs. regex).
     - Hybrid handoff rate (% of queries routed to regex).
     - Real-time accuracy metrics via sampling and human review.
   - Set alerts:
     - Alert if fallback rate > 30% or average latency > 20 ms.

4. **A/B Testing & Rollout**
   - Define clear success criteria:
     - 25% reduction in unnecessary RAG searches within first 2 weeks.
     - Maintain or improve user satisfaction scores.
   - Use feature flags for gradual rollout:
     - Start at 10% traffic → 50% → 100%.
     - Automate rollback if anomaly thresholds breached.

5. **Retraining & Maintenance**
   - Schedule periodic retraining (e.g., monthly) using combined synthetic + real data.
   - Monitor for new intents emerging in logs; update model and patterns accordingly.

6. **Documentation & Developer Onboarding**
   - Publish this file in `docs/` for engineering reference.
   - Add code comments linking to this plan.
   - Update README with hybrid routing overview and configuration options.

---

_End of document._
