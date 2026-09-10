"""Running many worlds at once, one per core.

A single soak is one seed's worth of luck. Eight seeds tell you far more about
whether the creature is sound, and they are perfectly independent - the sim
shares no state between worlds and is deterministic per seed - so they are the
one part of this program that genuinely wants a big CPU.

Threads would not do: the tick is pure Python and the GIL means threads share
one core's worth of bytecode. Processes each get their own interpreter, which
is why this uses multiprocessing and why the win is real.
"""

import multiprocessing
import os

from config import DEFAULT_CONFIG, Config
from sim.harness import SimStats, run_ticks


def available_workers() -> int:
    """How many processes this machine can usefully run."""
    return max(1, os.cpu_count() or 1)


def configured_workers() -> int:
    """The worker count the settings screen last saved, or one per core.

    Read from the same file the menu writes, which is the whole point of that
    file: a worker count set in the settings should be the one a soak uses.
    Before it existed the menu wrote the number into a config object that
    nothing outside that session ever read.
    """
    from settings_store import load_values

    stored = load_values().get("workers")
    if isinstance(stored, int) and stored >= 1:
        return stored
    return DEFAULT_CONFIG.soak_workers or available_workers()


def _run_one(job: tuple[int, int, Config]) -> SimStats:
    """Module-level so it can be pickled to a worker process."""
    ticks, seed, config = job
    return run_ticks(ticks, seed, config)


def run_many(
    ticks: int,
    seeds,
    config: Config = DEFAULT_CONFIG,
    workers: int | None = None,
) -> list[SimStats]:
    """Soak several seeds, in parallel when it is worth it.

    Falls back to running them in this process for a single worker or a single
    seed: starting a process pool to run one job costs more than the job saves,
    and the serial path is easier to debug when a soak turns up something.

    Results come back in seed order regardless of which worker finished first,
    so a parallel run and a serial one are directly comparable.
    """
    seeds = list(seeds)
    if not seeds:
        return []
    workers = available_workers() if workers is None else max(1, workers)
    workers = min(workers, len(seeds))
    jobs = [(ticks, seed, config) for seed in seeds]
    if workers == 1:
        return [_run_one(job) for job in jobs]
    with multiprocessing.Pool(processes=workers) as pool:
        return pool.map(_run_one, jobs)


def summarise(results: list[SimStats]) -> dict:
    """Aggregate a batch into the numbers worth reading at a glance."""
    if not results:
        return {}
    return {
        "worlds": len(results),
        "ticks_each": results[0].ticks,
        "kills": sum(r.kills for r in results),
        "deaths": sum(r.deaths for r in results),
        "max_distance": max(r.max_distance for r in results),
        "memory_peak": max(r.memory_peak for r in results),
        "starved_ticks": sum(r.frontier_starved_ticks for r in results),
        "worst_starved": max(r.frontier_starved_ticks for r in results),
        "levels": [r.final_level for r in results],
    }


def _report(results: list[SimStats]) -> None:
    for stats in results:
        print(
            f"  seed {stats.seed:<4} level {stats.final_level:<3} kills {stats.kills:<5}"
            f" deaths {stats.deaths:<3} reach {stats.max_distance:<5}"
            f" peak-memory {stats.memory_peak:<7} starved {stats.frontier_starved_ticks}"
        )
    print(summarise(results))


def main(argv: list[str] | None = None) -> None:
    """`python -m sim.soak [ticks] [worlds] [workers]`.

    A separate entry point from the game so that worker processes - which
    re-import the main module under Windows spawn - never load pygame. Running
    this through main.py works, but pays for a graphics library in every
    worker for nothing.
    """
    import sys

    argv = sys.argv[1:] if argv is None else argv
    ticks = int(argv[0]) if len(argv) > 0 else 2000
    worlds = int(argv[1]) if len(argv) > 1 else configured_workers()
    workers = int(argv[2]) if len(argv) > 2 else configured_workers()
    seeds = list(range(1, worlds + 1))
    print(f"soaking {len(seeds)} worlds x {ticks} ticks on {workers} workers...")
    _report(run_many(ticks, seeds, DEFAULT_CONFIG, workers=workers))


if __name__ == "__main__":
    main()
