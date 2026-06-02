# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A composite-ratings model and Monte-Carlo simulator for the 2026 FIFA World Cup, plus a static
web dashboard. Python estimates team strength, simulates the full 48-team tournament tens of
thousands of times, and writes `site/data.json`; the static `site/` renders it.

## Environment & commands

Python 3.9 with no global scientific packages — **always use the project venv** (`.venv/bin/python`,
or `source .venv/bin/activate` first). numpy/requests/beautifulsoup4 only exist there.

```bash
python fetch_ratings.py        # (re)populate the `elo` column in data/ratings.csv
python run.py                  # build composite -> simulate -> write site/data.json
python run.py --sims 100000 --seed 0   # override sim count / RNG seed

# preview the dashboard (must be served over http; the page fetch()es data.json)
cd site && python -m http.server 8000   # -> http://localhost:8000
```

There is no test suite or linter. Each `sim/` module has a `__main__` block used for ad-hoc
verification — run them as modules from the repo root, e.g.:

```bash
python -m sim.ratings        # print top-10 composite ratings
python -m sim.tournament     # validate all 495 third-place bracket combinations
python -m sim.simulate       # run a sim and print champion odds + invariant checks
```

## Pipeline / data flow

`data/*.csv` → `run.py` → `sim.simulate.run()` → `sim.export.write_json()` → `site/data.json` → `site/app.js`.

`run.py` is the single entry point. The whole simulation is **vectorized across all N simulations
at once** — nearly every array in `sim/simulate.py` has shape `(N, ...)` and there is no per-sim
Python loop. When editing the simulator, preserve this: operate on numpy arrays indexed by global
team id (0–47), not on individual matches/sims.

## Module responsibilities (`sim/`)

- `config.py` — all tunables: composite `WEIGHTS`, scale constants, the match-model constants, sim
  count, seed, host nations. Start here for any calibration change.
- `ratings.py` — `load_teams()`: reads `groups.csv` + `ratings.csv`, normalizes each active source
  to a common scale (mean 1500, sd 150), blends into a single `composite` per `Team`.
- `model.py` — Elo-style rating diff → Poisson `(lambda_a, lambda_b)` → scorelines; knockout tie
  resolution via softened win-expectancy. All functions are array-vectorized.
- `tournament.py` — the **static 2026 bracket structure** (official R32→Final tree, match numbers
  73–104) and the third-place-team → bracket-slot assignment solver.
- `simulate.py` — orchestrates the Monte-Carlo: group stage, third-place qualification, bracket
  assembly, knockout rounds; applies result-locking; returns counters.
- `export.py` — turns counters into the `data.json` payload (per-team stage probabilities + group
  finishing-position probabilities).

## Key architectural facts (non-obvious)

- **Data contracts are name-keyed.** `data/groups.csv` is the source of truth for the 48 team names
  and logo URLs. `ratings.csv` and `results.csv` must use **exactly** those names or rows are
  skipped with a warning. Global team id = row order in `groups.csv` (0–47).
- **Adding a rating source = one column + one weight.** Add a column to `ratings.csv` (one value
  per team; raw units don't matter, it's normalized) and register it in `config.WEIGHTS`. No code
  changes. With a single active source the composite just equals its normalized values.
- **Calibration coupling.** `ELO_PER_GOAL` is tuned against the fixed sd=150 normalized scale so the
  favorite lands ~22% to win. If you change `SCALE_SD`, the rating spread, or the source mix
  materially, re-check that goal totals (~2.7/match) and favorite odds stay realistic.
- **Third-place bracket assignment is solved, not FIFA's exact table.** FIFA's Annex C predefines a
  slot assignment for each of the C(12,8)=495 qualifying-third combinations; `tournament.py`
  instead solves the same hard constraints (slot eligibility + no same-group meetings) with a cached
  bipartite matching. Hard rules are honored; only the tiebreak among equally-valid assignments may
  differ, which doesn't affect aggregate probabilities.
- **Result-locking.** Any row in `data/results.csv` (`stage` = `group` or `ko`) forces that match's
  real outcome instead of simulating it; everything else is still simulated, so the forecast
  conditions on results as they come in. Drawn knockout matches need a 6th `winner` column.
- **Frontend is dependency-free.** `site/` is plain HTML/CSS/vanilla JS reading `data.json` (no build
  step, no framework). Tabs are hash-routed (`#groups` / `#knockout`). It must be served over http,
  not opened as a `file://` URL, because it `fetch()`es `data.json`.

See `README.md` for the user-facing update workflow.
