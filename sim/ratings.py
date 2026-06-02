"""Load teams and build the composite strength rating.

Reads data/groups.csv (teams, group, logo) and data/ratings.csv (one column per
rating source). Each active source named in config.WEIGHTS is normalized to a
common Elo-like scale, then combined as a weighted average into a single
`composite` rating per team.

With only `elo` active, the composite is just the normalized Elo, which (because
normalization is mean/sd based) preserves the exact ordering and relative spread
of the raw Elo numbers.
"""

import csv
from dataclasses import dataclass

import numpy as np

from sim import config


@dataclass
class Team:
    name: str
    group: str
    logo: str
    composite: float
    sources: dict  # raw per-source values that were available


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_float(value):
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _normalize(values):
    """Map a list of raw values to the common scale (config.SCALE_MEAN/SD).

    Missing entries (None) are imputed to the source's own mean so a team that
    lacks one source is treated as average by that source rather than dropped.
    """
    arr = np.array([v if v is not None else np.nan for v in values], dtype=float)
    present = arr[~np.isnan(arr)]
    if present.size == 0:
        return None  # source has no data at all -> skip it
    mean = present.mean()
    sd = present.std()
    arr = np.where(np.isnan(arr), mean, arr)
    if sd == 0:
        z = np.zeros_like(arr)
    else:
        z = (arr - mean) / sd
    return config.SCALE_MEAN + config.SCALE_SD * z


def load_teams():
    """Return a list of Team objects ordered as in groups.csv, with composite
    ratings filled in."""
    groups = _read_csv(config.GROUPS_CSV)
    ratings = {row["team"]: row for row in _read_csv(config.RATINGS_CSV)}

    team_names = [row["team"] for row in groups]

    # Build normalized, weighted composite across active sources.
    active = {src: w for src, w in config.WEIGHTS.items() if w > 0}
    if not active:
        raise ValueError("config.WEIGHTS has no active source with weight > 0")

    raw_per_source = {}
    norm_per_source = {}
    for src in active:
        raw = [_to_float(ratings.get(name, {}).get(src)) for name in team_names]
        normed = _normalize(raw)
        if normed is None:
            print(f"  NOTE: rating source '{src}' has no data; skipping it.")
            continue
        raw_per_source[src] = raw
        norm_per_source[src] = normed

    if not norm_per_source:
        raise ValueError("No active rating source had any usable data in ratings.csv")

    total_w = sum(active[src] for src in norm_per_source)
    composite = np.zeros(len(team_names))
    for src, normed in norm_per_source.items():
        composite += (active[src] / total_w) * normed

    # Re-standardize the blended composite back to the common scale. Averaging
    # several normalized sources shrinks the spread (the more so the less they
    # agree), so without this the effective strength gaps -- and thus the
    # match-model calibration in config.py -- would depend on how many sources
    # are active. Re-normalizing keeps the spread fixed regardless of source mix.
    csd = composite.std()
    if csd > 0:
        composite = config.SCALE_MEAN + config.SCALE_SD * (composite - composite.mean()) / csd

    teams = []
    for i, row in enumerate(groups):
        name = row["team"]
        sources = {
            src: raw_per_source[src][i]
            for src in norm_per_source
            if raw_per_source[src][i] is not None
        }
        teams.append(Team(
            name=name,
            group=row["group"],
            logo=row.get("logo", ""),
            composite=float(composite[i]),
            sources=sources,
        ))
    return teams


if __name__ == "__main__":
    teams = load_teams()
    for t in sorted(teams, key=lambda x: -x.composite)[:10]:
        print(f"{t.composite:7.1f}  {t.name} (group {t.group})")
