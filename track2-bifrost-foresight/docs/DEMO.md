# Judge demo — the 90-second track

Everything below works at `http://localhost:8400` with the demo processes running
(`powershell -File scripts/run-demo.ps1`, or see README quickstart for the three processes).

0. **Click “Reseed demo data”** in the top bar first. This re-anchors the 21-day fleet so the
   seeded story is fresh (this is by design: the demo is rolling-relative).

1. **Overview** — open with the story, not the data: "Growth Backend · prod is at 86% of its
   $500 rolling 30-day budget and is about to breach it. No incumbent gateway knows this."
   Point at the banner and the condition strip.

2. **The choir** — in the Fleet burn chart, the dashed line and the vermilion fan are the
   committee of 24 bootstrap trees, each a slightly different model of this gateway's demand.
   The band is its honest uncertainty. The fan widens with the horizon because each member
   sees lag differently — this is *calibrated* (the card on the Autopilot page says 80%
   coverage, measured out-of-sample).

3. **Ensemble breach risk** — in the Attention list, each risky key carries
   `ensemble paths $X vs $Y cap · breach Z% / 48h`. Drag a key's budget down on the Keys page
   and refresh: the remaining capacity tightens, and the probability jumps immediately.
   (GPU-free, live, honest.)

4. **Anomalies — two eyes** — the demo's 7.81× blowout hour reads **10.9σ** for the statistical
   detector and **15.8σ** for the trained expectation head — and the model finds the lower-level
   business-hours drift the z ≥ 3.5 threshold ignores. Both views, one number each side.

5. **Right-sizing › Demand stress test** — ask the committee a question Bifrost itself cannot
   answer: "what if this key spent ×3?". The fleet curve recomputes live through the same 24
   members. Fleet spend for 24h goes $34 → $60 on the seeded story — and the latency is honest:
   the ensemble re-derives, it does not interpolate.

6. **Webhook sink** — back to Overview → Alerts: click into **Autopilot › Webhook sink**, show a
   real payload Foresight fired when the budget projected to breach (not after it breaches).

7. **Autopilot › Forecast model** — the card shows the artifact (≈19 MB vs the 100 MB budget),
   val MAE vs naive same-hour-last-week baseline, and the band coverage. Click
   **“Retrain on live data”** if there is time — you will see the committee re-fit and the
   metrics refresh in seconds. Say the line out loud: "this is the same gateway, asking itself
   questions about its own metering."

## Suggested line

> "Everything you see is the same gateway — Bifrost open-source — pricing it, capping it,
> and telling itself its own future. The only code we wrote is the prediction layer; it runs
> beside Bifrost on purpose, not inside it, because predictive governance belongs where it can
> be audited."

## Honesty checklist (have answers for)

- **Governance ETAs stay statistical** (`forecast.py`), not ML — the model shapes the curve and
  the band; policy verdicts are byte-identical without the artifact. That is the Bifrost
  design philosophy: enforcement is arithmetic, not opinion.
- **No sklearn / artifact / capacity** → console falls back to burn-rate forecasts everywhere.
- **Trees saturate** past the envelope they trained on — the saturation in the stress panel is
  the feature, not a bug; in production you watch for it with drift monitors.
- **Seeded fleet** is simulated shape; metering, pricing, policy, and the ML path are real.
