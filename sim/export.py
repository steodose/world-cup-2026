"""Aggregate simulation counters into site/data.json for the dashboard."""

import json
from datetime import datetime, timezone

import numpy as np

from sim import config
from sim.tournament import GROUP_LETTERS


def build_payload(result):
    teams = result["teams"]
    n = result["n_sims"]
    pos = result["pos_counts"]
    points_sum = result["points_sum"]
    reach = result["reach"]

    team_rows = []
    for i, t in enumerate(teams):
        played = pos[i].sum()  # = n (each team finishes somewhere every sim)
        row = {
            "name": t.name,
            "group": t.group,
            "logo": t.logo,
            "rating": round(t.composite),
            "sources": {k: round(v, 1) for k, v in t.sources.items()},
            "proj_points": round(points_sum[i] / n, 2),
            "win_group": pos[i, 0] / n,
            "runner_up": pos[i, 1] / n,
            "third": pos[i, 2] / n,
            "fourth": pos[i, 3] / n,
            "advance": reach["round_of_32"][i] / n,  # reach knockout (R32)
            "round_of_32": reach["round_of_32"][i] / n,
            "round_of_16": reach["round_of_16"][i] / n,
            "quarter_finals": reach["quarter_finals"][i] / n,
            "semi_finals": reach["semi_finals"][i] / n,
            "final": reach["final"][i] / n,
            "champion": reach["champion"][i] / n,
        }
        team_rows.append(row)

    # Global rank (1 = strongest) by composite rating across all 48 teams.
    for rank, row in enumerate(sorted(team_rows, key=lambda r: -r["rating"]), start=1):
        row["rank"] = rank

    by_name = {r["name"]: r for r in team_rows}

    groups = []
    for letter in GROUP_LETTERS:
        members = [r for r in team_rows if r["group"] == letter]
        members.sort(key=lambda r: (-r["advance"], -r["proj_points"]))
        groups.append({"letter": letter, "teams": members})

    return {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "n_sims": n,
            "locked_group_matches": len(result["group_locks"]),
            "locked_ko_matches": len(result["ko_locks"]),
            "sources": [s for s, w in config.WEIGHTS.items() if w > 0],
        },
        "groups": groups,
        "teams": sorted(team_rows, key=lambda r: -r["champion"]),
    }


def write_json(result, path=None):
    path = path or config.DATA_JSON
    payload = build_payload(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # Also emit data.js, which assigns the payload to a global. This lets the
    # dashboard work when index.html is opened directly as a file:// URL, where
    # browsers block fetch() of data.json. The page prefers this global and
    # falls back to fetching data.json when served over http.
    js_path = path.with_suffix(".js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.WC_DATA = ")
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    return path
