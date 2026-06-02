"""Populate data/ratings.csv with World Football Elo ratings from eloratings.net.

Pulls the live world ratings table (https://www.eloratings.net/World.tsv), which
is a headerless TSV whose columns are:  rank | rank | country-code | elo | ...
Country codes are eloratings.net's own 2-letter codes (mostly ISO 3166-1 alpha-2,
but with custom codes for e.g. the UK home nations: England=EN, Scotland=SQ).

If the fetch fails, falls back to a baked-in table of recent values so the model
always has something to run with.

Usage:  python fetch_ratings.py

Only the `elo` column is written; any other source columns you have added by hand
(e.g. fifa, kuleuven, silver) for the composite are preserved.
"""

import csv
import sys

import requests

from sim import config

ELO_TSV_URL = "https://www.eloratings.net/World.tsv"

# Our team names -> eloratings.net 2-letter country codes.
TEAM_CODES = {
    "Mexico": "MX", "South Korea": "KR", "South Africa": "ZA",
    "Czech Republic": "CZ", "Canada": "CA", "Switzerland": "CH", "Qatar": "QA",
    "Bosnia & Herzegovina": "BA", "Brazil": "BR", "Morocco": "MA",
    "Scotland": "SQ", "Haiti": "HT", "USA": "US", "Australia": "AU",
    "Paraguay": "PY", "Turkey": "TR", "Germany": "DE", "Ecuador": "EC",
    "Ivory Coast": "CI", "Curaçao": "CW", "Netherlands": "NL", "Japan": "JP",
    "Tunisia": "TN", "Sweden": "SE", "Belgium": "BE", "Iran": "IR",
    "Egypt": "EG", "New Zealand": "NZ", "Spain": "ES", "Uruguay": "UY",
    "Saudi Arabia": "SA", "Cape Verde": "CV", "France": "FR", "Senegal": "SN",
    "Norway": "NO", "Iraq": "IQ", "Argentina": "AR", "Austria": "AT",
    "Algeria": "DZ", "Jordan": "JO", "Portugal": "PT", "Colombia": "CO",
    "Uzbekistan": "UZ", "DR Congo": "CD", "England": "EN", "Croatia": "HR",
    "Ghana": "GH", "Panama": "PA",
}

# Last-resort values if eloratings.net is unreachable (approximate).
FALLBACK_ELO = {
    "Argentina": 2113, "France": 2081, "Spain": 2165, "Brazil": 1988,
    "England": 2020, "Netherlands": 1961, "Portugal": 1984, "Germany": 1925,
    "Belgium": 1867, "Uruguay": 1892, "Colombia": 1975, "Croatia": 1930,
    "Morocco": 1822, "Switzerland": 1894, "Japan": 1906, "Senegal": 1866,
    "Austria": 1827, "Turkey": 1902, "Norway": 1917, "Ecuador": 1935,
    "Iran": 1764, "South Korea": 1756, "Sweden": 1714, "Mexico": 1868,
    "USA": 1733, "Ivory Coast": 1676, "Algeria": 1743, "Egypt": 1699,
    "Bosnia & Herzegovina": 1591, "Scotland": 1770, "Czech Republic": 1733,
    "Canada": 1784, "Paraguay": 1833, "Ghana": 1503, "DR Congo": 1655,
    "Australia": 1775, "South Africa": 1517, "Tunisia": 1636, "Uzbekistan": 1727,
    "Iraq": 1608, "Qatar": 1423, "Panama": 1733, "Cape Verde": 1576,
    "Jordan": 1685, "Saudi Arabia": 1566, "New Zealand": 1585, "Haiti": 1532,
    "Curaçao": 1433,
}


def load_team_names():
    with open(config.GROUPS_CSV, newline="", encoding="utf-8") as f:
        return [row["team"] for row in csv.DictReader(f)]


def scrape_eloratings():
    """Fetch the live world table. Returns {country_code: elo}, or {} on failure."""
    try:
        resp = requests.get(ELO_TSV_URL, timeout=20)
        resp.raise_for_status()
        out = {}
        for line in resp.text.splitlines():
            parts = line.split("\t")
            # rank | rank | code | elo | ...
            if len(parts) > 3 and parts[2].isalpha():
                try:
                    out[parts[2]] = int(parts[3])
                except ValueError:
                    continue
        return out
    except Exception as exc:  # noqa: BLE001 - any network/parse error -> fallback
        print(f"  (scrape failed: {exc}; using fallback table)", file=sys.stderr)
        return {}


def resolve(team, scraped):
    code = TEAM_CODES.get(team)
    if code and code in scraped:
        return scraped[code], "scraped"
    return FALLBACK_ELO.get(team), "fallback"


def main():
    teams = load_team_names()
    scraped = scrape_eloratings()

    # Preserve any extra source columns already present in ratings.csv.
    existing = {}
    extra_cols = []
    if config.RATINGS_CSV.exists():
        with open(config.RATINGS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            extra_cols = [c for c in (reader.fieldnames or []) if c not in ("team", "elo")]
            for row in reader:
                existing[row["team"]] = row

    n_scraped = 0
    rows = []
    for team in teams:
        elo, src = resolve(team, scraped)
        if elo is None:
            print(f"  WARNING: no Elo for {team!r}; leaving blank", file=sys.stderr)
            elo = ""
        if src == "scraped":
            n_scraped += 1
        row = {"team": team, "elo": elo}
        for col in extra_cols:
            row[col] = existing.get(team, {}).get(col, "")
        rows.append(row)

    fieldnames = ["team", "elo"] + extra_cols
    with open(config.RATINGS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} teams to {config.RATINGS_CSV} "
          f"({n_scraped} from eloratings.net, {len(rows) - n_scraped} from fallback).")
    if extra_cols:
        print(f"Preserved extra source columns: {', '.join(extra_cols)}")


if __name__ == "__main__":
    main()
