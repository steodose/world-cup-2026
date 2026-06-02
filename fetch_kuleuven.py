"""Add/update the `kuleuven` column in data/ratings.csv from the KU Leuven
(DTAI Sports Analytics Lab) 2026 World Cup model.

Their model publishes a ratings table at
https://dtai.cs.kuleuven.be/sports/worldcup2026/data/ratings.csv with columns
  Name, Elo, Odm_off, Off, Odm_def, Def
We use their `Elo` column as a single overall-strength rating per team (it gives
a clean, consensus ordering; the Off/Def split is their internal goal model).

If the fetch fails, falls back to a baked-in snapshot so the model still runs.
Existing columns in data/ratings.csv (e.g. elo) are preserved; only `kuleuven`
is written. After running this, add `"kuleuven"` to WEIGHTS in sim/config.py to
include it in the composite.

Usage:  python fetch_kuleuven.py
"""

import csv
import sys
import unicodedata

import requests

from sim import config


def _norm(name):
    """Normalize a team name for matching (NFC Unicode, trimmed)."""
    return unicodedata.normalize("NFC", name).strip()

KU_RATINGS_URL = "https://dtai.cs.kuleuven.be/sports/worldcup2026/data/ratings.csv"

# Our team names -> the Name used in KU Leuven's ratings table (where different).
TEAM_NAMES = {
    "USA": "United States",
    "Czech Republic": "Czechia",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}

# Last-resort snapshot of KU Leuven Elo if their site is unreachable.
FALLBACK_KU = {
    "Mexico": 1800, "South Korea": 1754, "South Africa": 1527, "Czech Republic": 1692,
    "Canada": 1741, "Switzerland": 1782, "Qatar": 1591, "Bosnia & Herzegovina": 1589,
    "Brazil": 1886, "Morocco": 1737, "Scotland": 1685, "Haiti": 1583, "USA": 1766,
    "Australia": 1747, "Paraguay": 1706, "Turkey": 1772, "Germany": 1867,
    "Ecuador": 1794, "Ivory Coast": 1619, "Curaçao": 1520, "Netherlands": 1868,
    "Japan": 1834, "Tunisia": 1583, "Sweden": 1701, "Belgium": 1817, "Iran": 1758,
    "Egypt": 1633, "New Zealand": 1599, "Spain": 1979, "Uruguay": 1803,
    "Saudi Arabia": 1617, "Cape Verde": 1489, "France": 1940, "Senegal": 1728,
    "Norway": 1747, "Iraq": 1653, "Argentina": 1965, "Austria": 1749, "Algeria": 1660,
    "Jordan": 1628, "Portugal": 1875, "Colombia": 1855, "Uzbekistan": 1712,
    "DR Congo": 1539, "England": 1886, "Croatia": 1821, "Ghana": 1478, "Panama": 1699,
}


def fetch_kuleuven():
    """Return {KU team Name: Elo}, or {} on failure."""
    try:
        resp = requests.get(KU_RATINGS_URL, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"  # the feed has no charset header; it is UTF-8
        out = {}
        reader = csv.DictReader(resp.text.splitlines())
        for row in reader:
            try:
                out[_norm(row["Name"])] = round(float(row["Elo"]))
            except (KeyError, ValueError, TypeError):
                continue
        return out
    except Exception as exc:  # noqa: BLE001 - any network/parse error -> fallback
        print(f"  (KU Leuven fetch failed: {exc}; using fallback table)", file=sys.stderr)
        return {}


def resolve(team, scraped):
    name = _norm(TEAM_NAMES.get(team, team))
    if name in scraped:
        return scraped[name], "fetched"
    return FALLBACK_KU.get(team), "fallback"


def main():
    if not config.RATINGS_CSV.exists():
        sys.exit("data/ratings.csv not found — run `python fetch_ratings.py` first.")

    with open(config.RATINGS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    scraped = fetch_kuleuven()
    if "kuleuven" not in fieldnames:
        fieldnames.append("kuleuven")

    n_fetched = 0
    for row in rows:
        elo, src = resolve(row["team"], scraped)
        if elo is None:
            print(f"  WARNING: no KU Leuven rating for {row['team']!r}", file=sys.stderr)
            elo = ""
        if src == "fetched":
            n_fetched += 1
        row["kuleuven"] = elo

    with open(config.RATINGS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated 'kuleuven' column for {len(rows)} teams in {config.RATINGS_CSV} "
          f"({n_fetched} from KU Leuven, {len(rows) - n_fetched} from fallback).")
    print("Remember to set WEIGHTS['kuleuven'] in sim/config.py to include it.")


if __name__ == "__main__":
    main()
