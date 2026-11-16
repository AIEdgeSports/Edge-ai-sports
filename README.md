# EDGE AI v0.1 — Probability Lab

This is a working **baseline calculator**, not a trained or validated AI model. All sample rows are fictional and not actionable picks.

## Run

Install Python 3.10+, then in this folder:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the localhost URL Streamlit prints. Use the single-market calculator or upload `sample_odds.csv` into the scanner.

## What works

- NBA, NFL, MLB labels; player props, moneyline, spread, totals
- Normal/Poisson distribution calculations (Poisson for count props/totals only)
- Multiple sportsbook comparison from manually provided CSV odds
- Implied probability, two-way proportional no-vig, expected return
- CSV export of ranked results

## Compare projections with manually recorded book lines

1. Use the scanner with your own projections, or load NBA/NFL automatic projections and download the comparison CSV. The export includes player, team, stat and games sampled. Match each row to the intended event and supply a standard deviation for the Normal model. Anytime TD frequencies stay in the projections table.
2. Enter the selection, book line, sportsbook and American odds. Put the other side's American price in `opposing_odds` on the same row. Use the same book, event, player/stat, line and odds snapshot for both prices. Enter the home team's line for spreads and 0 for moneylines.
3. Upload the CSV. The scanner displays the projection, book line, no-vig implied probability, model edge and row warnings. Missing inputs leave the affected metrics blank. Older uploads with only one price still show model probability and expected return when those inputs are complete.
4. Download the results for review. No-vig probability divides the selection's implied probability by the sum of both implied probabilities. Model edge is model probability minus no-vig probability in percentage points. Expected return uses the offered price, and rows with a computed return are ranked by it.

CSV inputs are `sport,market,selection,line,mean,sd,distribution,sportsbook,odds,opposing_odds`. Include `event` for exported projections and use `player`, `team` and `stat` to identify player markets. For Poisson, standard deviation can be blank. The sample CSV includes an intentionally one-sided quote.

## Important assumptions and limitations

- The calculator uses a supplied mean and standard deviation. The experimental NBA/NFL projection tab can export recent-game averages as the mean. A sport label does not change the probability model.
- Normal distribution is a rough approximation and is inappropriate for some outcomes; Poisson is unsuitable for overdispersed/correlated data. No injuries, minutes, weather, opponents, or line movement are ingested.
- For moneylines, `over` = home team wins and `under` = away team wins; projected mean is expected home scoring margin and sd its uncertainty.
- For spreads, `line` is the home-team spread, `over` = home covers, `under` = away covers; projected mean is home scoring margin.
- For totals, mean/sd refer to combined points/runs; for player props they refer to that player statistic.
- The normal model treats exact pushes as zero probability. Poisson integer lines condition on a non-push result for probability/EV (pushes return stakes, so the EV displayed for Poisson integer lines is conditional, not unconditional). Avoid integer lines for EV comparisons until a full three-outcome EV engine is added.
- Odds are manually imported, not live or licensed; commercial rights to statistics, odds, team logos, and league marks must be verified before launch.
- Positive estimated expected value does not guarantee profit. Verify against held-out results, calibration, and realistic betting costs.

## Production architecture

`Odds/stat feeds -> ingest jobs -> normalized Postgres tables -> feature store -> sport-specific trained models -> calibrated probability API -> odds comparison/EV service -> dashboard -> performance monitoring`.

Start with time-stamped historical data and walk-forward evaluation; do not claim predictive accuracy or sell subscriptions before validation.
