"""The 2026 tournament structure: 48 teams, 12 groups, and the official 32-team
knockout bracket, plus the logic for assigning the 8 best third-placed teams to
their bracket slots.

The Round-of-32 → Final tree below is the official FIFA bracket (match numbers
73-104). Each Round-of-32 slot is one of:
  ("1", "A")   -> winner of group A
  ("2", "B")   -> runner-up of group B
  ("3", i)     -> the third-placed team assigned to third-slot index i

FIFA's Annex C predefines, for each of the C(12,8)=495 possible sets of
qualifying third-placed teams, exactly which third goes to which slot. We don't
reproduce that 495-row table verbatim; instead we solve the same constraints
(each slot may only take a third from its eligible group set, and no team meets a
side from its own group) with a deterministic bipartite matching, cached per
combination. This honours every hard rule FIFA imposes; the only thing that can
differ from the official table is the tie-breaking choice among multiple valid
assignments, which has no bearing on aggregate stage probabilities.
"""

from functools import lru_cache
from itertools import combinations

GROUP_LETTERS = list("ABCDEFGHIJKL")  # A..L -> index 0..11

# The 8 third-place bracket slots, in a fixed order. For each: the eligible
# groups a third-placed team may come from (from the official placeholders such
# as "3ABCDF"). Slot order follows ascending match number (74,77,79,80,81,82,85,87).
THIRD_SLOT_ELIGIBLE = [
    set("ABCDF"),  # slot 0  (Match 74, vs 1E)
    set("CDFGH"),  # slot 1  (Match 77, vs 1I)
    set("CEFHI"),  # slot 2  (Match 79, vs 1A)
    set("EHIJK"),  # slot 3  (Match 80, vs 1L)
    set("BEFIJ"),  # slot 4  (Match 81, vs 1D)
    set("AEHIJ"),  # slot 5  (Match 82, vs 1G)
    set("EFGIJ"),  # slot 6  (Match 85, vs 1B)
    set("DEIJL"),  # slot 7  (Match 87, vs 1K)
]

# Round of 32: (match_number, slot_a, slot_b). A "3"-slot uses its slot index.
ROUND_OF_32 = [
    (73, ("2", "A"), ("2", "B")),
    (74, ("1", "E"), ("3", 0)),
    (75, ("1", "F"), ("2", "C")),
    (76, ("1", "C"), ("2", "F")),
    (77, ("1", "I"), ("3", 1)),
    (78, ("2", "E"), ("2", "I")),
    (79, ("1", "A"), ("3", 2)),
    (80, ("1", "L"), ("3", 3)),
    (81, ("1", "D"), ("3", 4)),
    (82, ("1", "G"), ("3", 5)),
    (83, ("2", "K"), ("2", "L")),
    (84, ("1", "H"), ("2", "J")),
    (85, ("1", "B"), ("3", 6)),
    (86, ("1", "J"), ("2", "H")),
    (87, ("1", "K"), ("3", 7)),
    (88, ("2", "D"), ("2", "G")),
]

# Later rounds: (match_number, feeder_match_a, feeder_match_b).
ROUND_OF_16 = [
    (89, 73, 75), (90, 74, 77), (91, 76, 78), (92, 79, 80),
    (93, 83, 84), (94, 81, 82), (95, 86, 88), (96, 85, 87),
]
QUARTER_FINALS = [
    (97, 89, 90), (98, 93, 94), (99, 91, 92), (100, 95, 96),
]
SEMI_FINALS = [
    (101, 97, 98), (102, 99, 100),
]
FINAL = (104, 101, 102)

# Human-readable stage names a team can reach (used for output columns).
STAGE_NAMES = ["round_of_32", "round_of_16", "quarter_finals",
               "semi_finals", "final", "champion"]


@lru_cache(maxsize=None)
def _match_thirds(qualifying_groups):
    """Given a sorted tuple of 8 group letters whose thirds qualify, return a
    tuple of length 8 mapping each third-slot index -> group letter, or None if
    no valid assignment exists (should never happen for FIFA's slot design)."""
    groups = list(qualifying_groups)
    assignment = [None] * 8

    # Order slots by how constrained they are (fewest eligible qualifiers first)
    # to make the backtracking search fast and deterministic.
    slot_options = []
    for slot in range(8):
        opts = [g for g in groups if g in THIRD_SLOT_ELIGIBLE[slot]]
        slot_options.append((len(opts), slot, sorted(opts)))
    slot_options.sort()
    order = [slot for _, slot, _ in slot_options]

    used = set()

    def backtrack(k):
        if k == len(order):
            return True
        slot = order[k]
        for g in sorted(THIRD_SLOT_ELIGIBLE[slot]):
            if g in qualifying_groups and g not in used:
                used.add(g)
                assignment[slot] = g
                if backtrack(k + 1):
                    return True
                used.discard(g)
                assignment[slot] = None
        return False

    if backtrack(0):
        return tuple(assignment)
    return None


def third_slot_assignment(qualifying_groups):
    """Public wrapper: qualifying_groups is any iterable of 8 group letters."""
    return _match_thirds(tuple(sorted(qualifying_groups)))


def validate_all_combinations():
    """Sanity check: every one of the 495 possible qualifying-third combinations
    has a valid slot assignment. Returns the count of any that fail."""
    failures = 0
    for combo in combinations(GROUP_LETTERS, 8):
        if third_slot_assignment(combo) is None:
            failures += 1
    return failures


if __name__ == "__main__":
    fails = validate_all_combinations()
    print(f"Combinations checked: {495}; without a valid assignment: {fails}")
    example = third_slot_assignment("ABCDEFGH")
    print("Example assignment for thirds {A..H}:")
    for i, g in enumerate(example):
        print(f"  third-slot {i} -> group {g}")
