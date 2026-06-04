"""Per-match win/draw/loss predictions for the scheduled fixtures.

Reads data/fixtures.csv (the static 2026 schedule), turns each matchup into a
win/draw/loss split using the *same* rating gap and host edge the Monte-Carlo
simulator uses, and merges in any played result from data/results.csv. The
output feeds the dashboard's match-by-match view.

The W/D/L split is computed analytically from the two Poisson scoring rates
(no simulation needed): build the joint scoreline grid P(a=i, b=j) and sum the
mass below / on / above the diagonal.
"""

import csv
from math import factorial

import numpy as np

from sim import config, model


def _poisson_pmf(lam, kmax):
    k = np.arange(kmax + 1)
    fact = np.array([factorial(int(x)) for x in k], dtype=np.float64)
    return np.exp(-lam) * np.power(float(lam), k) / fact


def wdl_probs(lam_a, lam_b, kmax=15):
    """P(team A wins), P(draw), P(team B wins) from the two scoring rates."""
    pa = _poisson_pmf(lam_a, kmax)
    pb = _poisson_pmf(lam_b, kmax)
    grid = np.outer(pa, pb)
    grid /= grid.sum()  # renormalize the tiny mass lost past kmax
    p_a = np.tril(grid, -1).sum()   # a goals > b goals
    p_draw = np.trace(grid)         # equal
    p_b = 1.0 - p_a - p_draw
    return float(p_a), float(p_draw), float(p_b)


def _load_played(name_to_team):
    """Map frozenset({name_a, name_b}) -> {name: goals} for group results."""
    played = {}
    if not config.RESULTS_CSV.exists():
        return played
    with open(config.RESULTS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ta, tb = row.get("team_a", "").strip(), row.get("team_b", "").strip()
            if ta not in name_to_team or tb not in name_to_team:
                continue
            try:
                ga, gb = int(row["score_a"]), int(row["score_b"])
            except (KeyError, ValueError):
                continue
            played[frozenset((ta, tb))] = {ta: ga, tb: gb}
    return played


def build_matches(teams):
    """Return a list of match dicts (predictions + any played result)."""
    name_to_team = {t.name: t for t in teams}
    host_bonus = {
        t.name: (config.HOST_HOME_ADVANTAGE if t.name in config.HOST_NATIONS else 0.0)
        for t in teams
    }
    played = _load_played(name_to_team)

    if not config.FIXTURES_CSV.exists():
        return []

    matches = []
    with open(config.FIXTURES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            na, nb = row["team_a"].strip(), row["team_b"].strip()
            ta, tb = name_to_team.get(na), name_to_team.get(nb)
            if ta is None or tb is None:
                print(f"  WARNING: fixtures.csv references unknown team(s): "
                      f"{na!r}/{nb!r}; skipping match {row.get('match_no')}.")
                continue

            diff = (ta.composite - tb.composite
                    + host_bonus[na] - host_bonus[nb])
            lam_a, lam_b = model.expected_goals(diff)
            p_a, p_draw, p_b = wdl_probs(float(lam_a), float(lam_b))

            entry = {
                "match_no": int(row["match_no"]),
                "date": row["date"].strip(),
                "venue": row["venue"].strip(),
                "stage": row.get("stage", "group").strip(),
                "group": row.get("group", "").strip(),
                "team_a": {"name": na, "logo": ta.logo},
                "team_b": {"name": nb, "logo": tb.logo},
                "xg_a": round(float(lam_a), 2),
                "xg_b": round(float(lam_b), 2),
                "p_a": round(p_a, 4),
                "p_draw": round(p_draw, 4),
                "p_b": round(p_b, 4),
                "played": False,
            }

            lock = played.get(frozenset((na, nb)))
            if lock is not None:
                entry["played"] = True
                entry["score_a"] = lock[na]
                entry["score_b"] = lock[nb]

            matches.append(entry)

    matches.sort(key=lambda m: (m["date"], m["match_no"]))
    return matches


if __name__ == "__main__":
    from sim.ratings import load_teams
    ms = build_matches(load_teams())
    print(f"{len(ms)} matches\n")
    for m in ms[:8]:
        a, b = m["team_a"]["name"], m["team_b"]["name"]
        print(f"  {m['date']}  {a:>22} {m['p_a']*100:4.0f}% / "
              f"{m['p_draw']*100:3.0f}% / {m['p_b']*100:4.0f}%  {b}")
