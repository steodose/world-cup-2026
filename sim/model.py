"""The match model: turn composite ratings into simulated scorelines/outcomes.

All functions are vectorized over an array of simultaneous matches (one entry per
Monte-Carlo simulation), so the whole tournament can be simulated for N sims at
once with numpy.
"""

import numpy as np

from sim import config


def expected_goals(rating_diff):
    """Map a rating difference (team A minus team B, including any home edge) to
    each side's expected goals (lambda_a, lambda_b)."""
    supremacy = rating_diff / config.ELO_PER_GOAL
    lam_a = np.maximum(config.MIN_LAMBDA, (config.AVG_TOTAL_GOALS + supremacy) / 2.0)
    lam_b = np.maximum(config.MIN_LAMBDA, (config.AVG_TOTAL_GOALS - supremacy) / 2.0)
    return lam_a, lam_b


def simulate_scorelines(rating_diff, rng):
    """Draw Poisson goals for both sides. Returns (goals_a, goals_b) int arrays."""
    lam_a, lam_b = expected_goals(rating_diff)
    goals_a = rng.poisson(lam_a)
    goals_b = rng.poisson(lam_b)
    return goals_a, goals_b


def win_expectancy(rating_diff):
    """Elo win-expectancy for team A: 1 / (10^(-diff/400) + 1)."""
    return 1.0 / (np.power(10.0, -rating_diff / 400.0) + 1.0)


def knockout_winners(rating_diff, goals_a, goals_b, rng):
    """Decide knockout winners. Team A wins on a higher score; ties are resolved
    by a softened win-expectancy draw (extra time / penalties).

    Returns a boolean array: True where team A advances.
    """
    a_wins = goals_a > goals_b
    b_wins = goals_b > goals_a
    tied = ~(a_wins | b_wins)

    we = win_expectancy(rating_diff)
    p_a = we * (1.0 - config.KO_SOFTEN) + 0.5 * config.KO_SOFTEN
    tie_a_wins = rng.random(rating_diff.shape) < p_a

    return np.where(tied, tie_a_wins, a_wins)
