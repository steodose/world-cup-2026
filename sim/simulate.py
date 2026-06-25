"""Monte-Carlo simulation of the whole tournament, vectorized across N sims.

Group stage and every knockout round are simulated for all N simulations at once
using numpy arrays of team indices, which keeps 50k full-tournament runs to a few
seconds. Any match listed in data/results.csv is locked to its real outcome
rather than simulated, so the forecast conditions on results as they come in.
"""

import csv
from itertools import combinations

import numpy as np

from sim import config, model
from sim.ratings import load_teams
from sim.tournament import (
    GROUP_LETTERS, ROUND_OF_32, ROUND_OF_16, QUARTER_FINALS, SEMI_FINALS,
    FINAL, third_slot_assignment,
)

# The 6 round-robin fixtures within a 4-team group (local indices 0..3).
GROUP_FIXTURES = list(combinations(range(4), 2))


def _load_results(name_to_id):
    """Parse data/results.csv into group score-locks and knockout winner-locks."""
    group_locks = {}   # frozenset({idA,idB}) -> {id: goals}
    ko_locks = []      # list of (idA, idB, winner_id)
    if not config.RESULTS_CSV.exists():
        return group_locks, ko_locks

    with open(config.RESULTS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ta, tb = row.get("team_a", "").strip(), row.get("team_b", "").strip()
            if not ta and not tb:
                continue
            if ta not in name_to_id or tb not in name_to_id:
                print(f"  WARNING: results.csv references unknown team(s): "
                      f"{ta!r}/{tb!r}; skipping row.")
                continue
            ida, idb = name_to_id[ta], name_to_id[tb]
            try:
                ga, gb = int(row["score_a"]), int(row["score_b"])
            except (KeyError, ValueError):
                print(f"  WARNING: bad score for {ta} vs {tb}; skipping row.")
                continue
            stage = row.get("stage", "group").strip().lower()
            if stage in ("group", "g", ""):
                group_locks[frozenset((ida, idb))] = {ida: ga, idb: gb}
            else:
                if ga > gb:
                    winner = ida
                elif gb > ga:
                    winner = idb
                else:
                    w = row.get("winner", "").strip()
                    if w not in name_to_id:
                        print(f"  WARNING: drawn knockout {ta} vs {tb} needs a "
                              f"'winner' column; skipping row.")
                        continue
                    winner = name_to_id[w]
                ko_locks.append((ida, idb, winner))
    return group_locks, ko_locks


def _rank_key(points, gd, gf, rng):
    """A single sortable key encoding points > goal difference > goals for, with
    a uniform random tiebreaker. Higher is better.

    Used for cross-group ranking of third-placed teams, where head-to-head does
    not apply (those teams never met). For ranking *within* a group, use
    `_group_order`, which inserts the 2026 head-to-head criteria."""
    rand = rng.random(points.shape)
    return points * 1e7 + gd * 1e3 + gf * 1.0 + rand


def _group_order(pts, gd, gf, h2h_pts, h2h_gd, h2h_gf, rng):
    """Best-first ordering of the 4 teams in each group under the 2026 World Cup
    tie-breaking rules, vectorized over sims. Shapes: per-team stats are (N, 4);
    head-to-head stats are (N, 4) mini-table sums already restricted to the tied
    teams. Criteria, most significant first:

        overall points > H2H points > H2H goal difference > H2H goals for
        > overall goal difference > overall goals for > random

    The defining 2026 change is that the head-to-head mini-table (among teams
    level on overall points) outranks overall goal difference.

    np.lexsort treats its *last* key as primary and sorts ascending, so we list
    keys least-significant first and reverse to get best-first. (Limitation: the
    mini-table is computed once over all teams level on points; FIFA's exact rule
    re-applies the H2H criteria recursively to any still-tied subset — a rare
    edge case in 3-way ties that this does not unwind.)"""
    rand = rng.random(pts.shape)
    keys = np.stack([rand, gf, gd, h2h_gf, h2h_gd, h2h_pts, pts])  # primary last
    order = np.lexsort(keys, axis=-1)        # ascending, worst-first
    return order[:, ::-1]                    # best-first


def run(n_sims=None, seed=None, verbose=True):
    n_sims = n_sims or config.N_SIMS
    seed = config.RANDOM_SEED if seed is None else seed
    rng = np.random.default_rng(seed)

    teams = load_teams()
    n_teams = len(teams)
    name_to_id = {t.name: i for i, t in enumerate(teams)}
    ratings = np.array([t.composite for t in teams])
    host_bonus = np.array([
        config.HOST_HOME_ADVANTAGE if t.name in config.HOST_NATIONS else 0.0
        for t in teams
    ])

    # group letter -> the 4 global team ids in that group (CSV order)
    group_ids = {g: [] for g in GROUP_LETTERS}
    for i, t in enumerate(teams):
        group_ids[t.group].append(i)
    for g, ids in group_ids.items():
        if len(ids) != 4:
            raise ValueError(f"Group {g} has {len(ids)} teams (expected 4).")

    group_locks, ko_locks = _load_results(name_to_id)
    if verbose:
        print(f"Loaded {len(teams)} teams. "
              f"Locked results: {len(group_locks)} group, {len(ko_locks)} knockout.")

    N = n_sims

    # --- output accumulators -------------------------------------------------
    # finishing-position counts per team: columns = [1st, 2nd, 3rd, 4th]
    pos_counts = np.zeros((n_teams, 4), dtype=np.int64)
    points_sum = np.zeros(n_teams, dtype=np.float64)
    reach = {s: np.zeros(n_teams, dtype=np.int64) for s in
             ["round_of_32", "round_of_16", "quarter_finals",
              "semi_finals", "final", "champion"]}

    # per-group, per-sim finishing team ids and third-place stats
    first_id = np.zeros((N, 12), dtype=np.int64)
    second_id = np.zeros((N, 12), dtype=np.int64)
    third_id = np.zeros((N, 12), dtype=np.int64)
    third_pts = np.zeros((N, 12), dtype=np.float64)
    third_gd = np.zeros((N, 12), dtype=np.float64)
    third_gf = np.zeros((N, 12), dtype=np.float64)

    def host_diff(id_a, id_b):
        return ratings[id_a] - ratings[id_b] + host_bonus[id_a] - host_bonus[id_b]

    # --- group stage ---------------------------------------------------------
    for gi, g in enumerate(GROUP_LETTERS):
        ids = np.array(group_ids[g])
        pts = np.zeros((N, 4), dtype=np.float64)
        gf = np.zeros((N, 4), dtype=np.float64)
        ga = np.zeros((N, 4), dtype=np.float64)  # goals against
        # per-pair head-to-head record, [:, i, j] = team i's result vs team j
        hh_pts = np.zeros((N, 4, 4), dtype=np.float64)
        hh_gf = np.zeros((N, 4, 4), dtype=np.float64)
        hh_ga = np.zeros((N, 4, 4), dtype=np.float64)

        for a, b in GROUP_FIXTURES:
            ida, idb = int(ids[a]), int(ids[b])
            lock = group_locks.get(frozenset((ida, idb)))
            if lock is not None:
                goals_a = np.full(N, lock[ida], dtype=np.int64)
                goals_b = np.full(N, lock[idb], dtype=np.int64)
            else:
                diff = host_diff(ida, idb)
                lam_a, lam_b = model.expected_goals(diff)
                goals_a = rng.poisson(lam_a, size=N)
                goals_b = rng.poisson(lam_b, size=N)

            pa = np.where(goals_a > goals_b, 3, np.where(goals_a == goals_b, 1, 0))
            pb = np.where(goals_b > goals_a, 3, np.where(goals_b == goals_a, 1, 0))
            pts[:, a] += pa
            pts[:, b] += pb
            gf[:, a] += goals_a; ga[:, a] += goals_b
            gf[:, b] += goals_b; ga[:, b] += goals_a
            hh_pts[:, a, b] = pa;      hh_pts[:, b, a] = pb
            hh_gf[:, a, b] = goals_a;  hh_gf[:, b, a] = goals_b
            hh_ga[:, a, b] = goals_b;  hh_ga[:, b, a] = goals_a

        gd = gf - ga

        # 2026 head-to-head mini-table: restrict each team's H2H record to the
        # opponents it is level with on overall points, then sum.
        level = (pts[:, :, None] == pts[:, None, :])        # (N,4,4)
        level &= ~np.eye(4, dtype=bool)[None]               # drop self
        h2h_pts = (hh_pts * level).sum(axis=2)              # (N,4)
        h2h_gd = ((hh_gf - hh_ga) * level).sum(axis=2)
        h2h_gf = (hh_gf * level).sum(axis=2)

        order = _group_order(pts, gd, gf, h2h_pts, h2h_gd, h2h_gf, rng)  # best-first

        # global ids by finishing position
        ids_by_pos = ids[order]                      # (N,4) global ids
        first_id[:, gi] = ids_by_pos[:, 0]
        second_id[:, gi] = ids_by_pos[:, 1]
        third_id[:, gi] = ids_by_pos[:, 2]

        # third-place stats for cross-group ranking
        rows = np.arange(N)
        third_pos = order[:, 2]
        third_pts[:, gi] = pts[rows, third_pos]
        third_gd[:, gi] = gd[rows, third_pos]
        third_gf[:, gi] = gf[rows, third_pos]

        # accumulate per-team finishing-position counts and points
        pts_by_pos = np.take_along_axis(pts, order, axis=1)
        for pos in range(4):
            np.add.at(pos_counts[:, pos], ids_by_pos[:, pos], 1)
            np.add.at(points_sum, ids_by_pos[:, pos], pts_by_pos[:, pos])

    # --- pick the 8 best third-placed teams ----------------------------------
    key3 = _rank_key(third_pts, third_gd, third_gf, rng)  # (N,12)
    order3 = np.argsort(-key3, axis=1)                    # group indices, best-first
    qualifying = order3[:, :8]                            # (N,8) qualifying group idx

    # combination bitmask per sim -> slot assignment lookup
    bitmask = np.zeros(N, dtype=np.int64)
    for k in range(8):
        bitmask |= (1 << qualifying[:, k])
    unique_keys, inverse = np.unique(bitmask, return_inverse=True)

    lut = np.zeros((len(unique_keys), 8), dtype=np.int64)
    letter_to_idx = {g: i for i, g in enumerate(GROUP_LETTERS)}
    for row_i, key_val in enumerate(unique_keys):
        qual_groups = [GROUP_LETTERS[b] for b in range(12) if key_val & (1 << b)]
        assignment = third_slot_assignment(qual_groups)  # slot -> letter
        lut[row_i] = [letter_to_idx[assignment[s]] for s in range(8)]
    slot_group_idx = lut[inverse]                         # (N,8) group idx per slot
    third_for_slot = np.take_along_axis(third_id, slot_group_idx, axis=1)  # (N,8)

    # --- assemble the Round of 32 --------------------------------------------
    def resolve_slot(slot):
        kind, ref = slot
        if kind == "1":
            return first_id[:, letter_to_idx[ref]]
        if kind == "2":
            return second_id[:, letter_to_idx[ref]]
        return third_for_slot[:, ref]  # kind == "3"

    def play_ko(id_a, id_b):
        diff = host_diff(id_a, id_b)
        lam_a, lam_b = model.expected_goals(diff)
        goals_a = rng.poisson(lam_a)
        goals_b = rng.poisson(lam_b)
        a_wins = model.knockout_winners(diff, goals_a, goals_b, rng)
        winner = np.where(a_wins, id_a, id_b)
        for lx, ly, w in ko_locks:
            mask = ((id_a == lx) & (id_b == ly)) | ((id_a == ly) & (id_b == lx))
            if mask.any():
                winner = np.where(mask, w, winner)
        return winner

    winners = {}   # match_number -> winner ids (N,)

    for m, slot_a, slot_b in ROUND_OF_32:
        id_a, id_b = resolve_slot(slot_a), resolve_slot(slot_b)
        np.add.at(reach["round_of_32"], id_a, 1)
        np.add.at(reach["round_of_32"], id_b, 1)
        w = play_ko(id_a, id_b)
        winners[m] = w
        np.add.at(reach["round_of_16"], w, 1)

    def play_round(matches, reach_key):
        for m, fa, fb in matches:
            w = play_ko(winners[fa], winners[fb])
            winners[m] = w
            np.add.at(reach[reach_key], w, 1)

    play_round(ROUND_OF_16, "quarter_finals")
    play_round(QUARTER_FINALS, "semi_finals")
    play_round(SEMI_FINALS, "final")

    m, fa, fb = FINAL
    champ = play_ko(winners[fa], winners[fb])
    winners[m] = champ
    np.add.at(reach["champion"], champ, 1)

    return {
        "teams": teams,
        "n_sims": N,
        "pos_counts": pos_counts,
        "points_sum": points_sum,
        "reach": reach,
        "group_locks": group_locks,
        "ko_locks": ko_locks,
    }


if __name__ == "__main__":
    res = run()
    teams = res["teams"]
    champ = res["reach"]["champion"] / res["n_sims"]
    order = np.argsort(-champ)
    print("\nTop 12 by championship probability:")
    for i in order[:12]:
        print(f"  {champ[i]*100:5.1f}%  {teams[i].name}")
    # invariants
    N = res["n_sims"]
    for s, expected in [("round_of_32", 32), ("round_of_16", 16),
                        ("quarter_finals", 8), ("semi_finals", 4),
                        ("final", 2), ("champion", 1)]:
        total = res["reach"][s].sum() / N
        print(f"  sum P({s}) = {total:.3f} (expect {expected})")
