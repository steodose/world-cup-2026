"""Entry point: build composite ratings, simulate the tournament, write data.json.

Usage:
    python run.py                 # default N_SIMS from sim/config.py
    python run.py --sims 100000   # override simulation count
    python run.py --seed 0        # override RNG seed (use a fresh draw)
"""

import argparse
import time

from sim import config, export, simulate


def main():
    parser = argparse.ArgumentParser(description="2026 World Cup simulator")
    parser.add_argument("--sims", type=int, default=config.N_SIMS,
                        help=f"number of Monte-Carlo simulations (default {config.N_SIMS})")
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED,
                        help="RNG seed for reproducibility")
    args = parser.parse_args()

    start = time.time()
    result = simulate.run(n_sims=args.sims, seed=args.seed)
    path = export.write_json(result)
    elapsed = time.time() - start

    teams = result["teams"]
    champ = result["reach"]["champion"]
    n = result["n_sims"]
    order = sorted(range(len(teams)), key=lambda i: -champ[i])
    print(f"\nWrote {path} ({n:,} sims in {elapsed:.1f}s)")
    print("Title favorites:")
    for i in order[:5]:
        print(f"  {champ[i] / n * 100:5.1f}%  {teams[i].name}")


if __name__ == "__main__":
    main()
