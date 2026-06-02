"""Tunable parameters for the 2026 World Cup model.

Everything a user might want to adjust lives here: which rating sources feed the
composite and how heavily, how Elo differences map to goals, and how many
simulations to run.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"

GROUPS_CSV = DATA_DIR / "groups.csv"
RATINGS_CSV = DATA_DIR / "ratings.csv"
RESULTS_CSV = DATA_DIR / "results.csv"
DATA_JSON = SITE_DIR / "data.json"

# Tidy CSV of the latest simulation, committed to the repo so anyone can do
# further analysis without running the model. Regenerated on every `run.py`.
SIMS_CSV = DATA_DIR / "simulations.csv"

# ---------------------------------------------------------------------------
# Composite ratings
# ---------------------------------------------------------------------------
# Each key is a column name in data/ratings.csv. The weight is its relative
# contribution to the composite. Sources are individually normalized to a
# common Elo-like scale (mean 1500, sd 150) before being combined, so the raw
# units of each source do not matter -- only the relative ordering/spread.
#
# To add a source later (e.g. Nate Silver): add its column to ratings.csv and
# add an entry here. With a single active source the composite just equals it.
WEIGHTS = {
    "elo": 0.40,       # World Football Elo (eloratings.net)
    "kuleuven": 0.60,  # KU Leuven DTAI model Elo
    # "fifa": 0.0,
    # "silver": 0.0,
}

# Common scale that every normalized source is mapped onto.
SCALE_MEAN = 1500.0
SCALE_SD = 150.0

# ---------------------------------------------------------------------------
# Match model (Elo difference -> expected goals)
# ---------------------------------------------------------------------------
# Expected goal supremacy = rating_diff / ELO_PER_GOAL, on the composite's
# common scale (mean 1500, sd 150). Calibrated so the pre-tournament favorite
# lands around ~22% to win the cup and per-match goal totals/draw rates are
# realistic; lower = more lopsided, higher = more parity.
ELO_PER_GOAL = 350.0

# Baseline expected total goals in an average match (recent World Cups ~2.6-2.8).
AVG_TOTAL_GOALS = 2.7

# Minimum lambda so a heavy underdog still has a non-zero scoring chance.
MIN_LAMBDA = 0.05

# Home advantage in Elo points, applied only to a host nation playing in its own
# country (USA, Mexico, Canada). The World Cup is otherwise on neutral ground.
HOST_HOME_ADVANTAGE = 50.0
HOST_NATIONS = {"USA", "Mexico", "Canada"}

# Knockout tiebreak: when regulation is a draw, the winner is drawn with
# probability We (Elo win-expectancy), pulled toward 0.5 by KO_SOFTEN to reflect
# the extra randomness of extra-time/penalties. 0 = pure Elo, 1 = coin flip.
KO_SOFTEN = 0.35

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
N_SIMS = 50_000
RANDOM_SEED = 20260611  # set to None for a fresh draw each run
