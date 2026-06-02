# 2026 World Cup Forecast

A composite-ratings model and Monte-Carlo simulator for the 2026 FIFA World Cup,
with a static web dashboard.

It estimates each team's strength from a **composite of public rating systems**,
turns rating differences into per-match scoreline probabilities, and runs tens of
thousands of **Monte-Carlo simulations** of the full 48-team tournament to estimate
each team's chance of reaching every stage — from advancing out of the group to
lifting the cup. Results are rendered in a light, sortable dashboard.

## Quick start

```bash
# one-time
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# build ratings -> simulate -> write site/data.json + simulations.csv
python fetch_ratings.py        # seed/refresh the Elo column in data/ratings.csv
python run.py                  # run the simulation

# view the dashboard
cd site && python -m http.server 8000   # then open http://localhost:8000
```

`python run.py --sims 100000 --seed 0` overrides the simulation count / RNG seed.

## How it works

1. **Composite ratings** (`sim/ratings.py`, `sim/config.py`). `data/ratings.csv`
   holds one column per rating source. Each active source listed in
   `config.WEIGHTS` is normalized to a common scale (mean 1500, sd 150) and the
   sources are blended into a single `composite` strength per team.
2. **Match model** (`sim/model.py`). The rating gap maps to an expected goal
   supremacy; each side's goals are drawn from a Poisson distribution, giving
   win/draw/loss plus the goal difference and goals-for needed for group
   tiebreakers. Knockout ties are decided by a softened win-expectancy
   (extra time / penalties). Constants are calibrated in `config.py` so the
   pre-tournament favorite sits around ~22% and match goal totals are realistic.
3. **Simulation** (`sim/tournament.py`, `sim/simulate.py`). The real 2026 format:
   12 groups of 4, top two plus the eight best third-placed teams advance, then
   the official Round-of-32 → Final bracket (with the third-place teams assigned
   to bracket slots under FIFA's eligibility rules). Everything is vectorized
   across all simulations with numpy, so 50,000 tournaments run in well under a
   second.

## Updating the forecast

**Add/replace rating sources (the composite).**
- Run `python fetch_ratings.py` to (re)populate the `elo` column (eloratings.net).
- Run `python fetch_kuleuven.py` to (re)populate the `kuleuven` column (KU Leuven
  DTAI model). The composite ships blending these two 50/50 (see `WEIGHTS` in
  `sim/config.py`).
- To add another source (e.g. FIFA ranking, Nate Silver): add a new column to
  `data/ratings.csv` with one value per team, then add that column name to
  `WEIGHTS` in `sim/config.py` with a weight. No other code changes needed. Raw
  units don't matter — each source is normalized, and the blended composite is
  re-standardized to a common scale before simulating.

**After matches are played.** Add a row to `data/results.csv`:

```csv
stage,team_a,team_b,score_a,score_b
group,Mexico,South Korea,2,1
ko,Brazil,Morocco,1,1,Brazil       # knockout draw -> add a 6th "winner" column
```

`stage` is `group` for group matches or `ko` for any knockout match. Locked
matches use their real score/outcome instead of being simulated; everything else
is still simulated, so the forecast conditions on results as they come in.

Then re-run `python run.py` and refresh the page.

## Files

```
data/groups.csv     teams, group, logo URL  (source of truth for names + logos)
data/ratings.csv    one column per rating source (elo, + any you add)
data/results.csv    played matches to lock (blank until the tournament starts)
sim/                config, ratings, match model, bracket, simulator, export
fetch_ratings.py    populate the Elo column (scrape + baked-in fallback)
run.py              build ratings -> simulate -> write site/data.json
site/               static dashboard (index.html, style.css, app.js, data.json)
data/simulations.csv  latest sim as a tidy CSV (one row per team) for analysis
```

`simulations.csv` is regenerated on every `python run.py` and committed to the
repo, so anyone can download it and do further analysis without running the
model. It has one row per team with the global rank, composite rating, each
source rating (`rating_elo`, `rating_kuleuven`, …), projected group points, and
every stage probability as a 0–1 fraction.

The `site/` folder is fully static and can be deployed as-is to GitHub Pages or
any static host.
