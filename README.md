# CFB Prop Engine v1.0

College-football conversion of the football projection architecture. This build is intentionally separate from the NFL source file.

## Live data
- CollegeFootballData (CFBD): games, player stats, AP/CFP rankings, SP+, CORE, SRS, Elo, talent, advanced team context.
- The Odds API: NCAA football moneyline, spreads, totals and supported player props.
- Weather/depth/injury adapter files are included for game-day context.

Set `CFBD_API_KEY` and optionally `ODDS_API_KEY` in Railway variables or `.streamlit/secrets.toml`. Never commit real keys.

## Core modeling
### Moneyline / spread
Uses SP+, CORE, SRS, Elo, roster talent and home field. AP rank is contextual only. A market spread, when available, is a small stabilizer/audit rather than the driver.

### Game total
Uses offensive/defensive ratings, pace and explosiveness to build expected points, then separates home/away scoring using the model margin.

### CFB blowout engine
Projected margin + talent gap → blowout probability. Favorite QB/WR/RB1 workload receives a playing-time tax when blowout probability is high. Underdog passing volume can receive catch-up-game-script volume.

### Player props
Opportunity-first formulas:
- Passing yards = expected passing production adjusted by pass script, pace, opponent pass defense, explosiveness/havoc and blowout workload.
- Receiving yards = receiving opportunity adjusted by expected pass volume and opponent pass/explosive matchup.
- Rushing yards = expected rushing opportunity/game script adjusted by opponent rush defense/havoc.
- Receptions, completions and attempts use their own volume distributions.
- Confidence is calculated from projection-vs-line divided by a market-specific standard deviation, not an arbitrary confidence score.

## Railway deployment
The repo includes `Procfile`, `runtime.txt`, `railway.json`, `.streamlit/config.toml`, environment templates and data adapter templates.

1. Deploy this GitHub repo on Railway.
2. Add `CFBD_API_KEY`.
3. Add `ODDS_API_KEY` if you want automatic sportsbook lines and props.
4. Railway will start the Streamlit app on `$PORT`.

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8080 --server.address 0.0.0.0
```

## Optional cache warmer
```bash
CFBD_API_KEY=... CFB_YEAR=2026 CFB_WEEK=2 python scripts/bootstrap_cfb_data.py
```

## Manual context adapters
`data/injuries.csv`: injury/availability and expected snap percentage.

`data/depth_chart.csv`: starter/backup depth order.

`data/game_context.csv`: temperature, wind, rain, neutral-site and altitude context.

College injury/depth reporting is inconsistent, so the app does not assume missing injury information means a player is healthy.
