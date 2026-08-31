"""
Benchmark the SALI chaos checker against billiards whose dynamics are
established in the literature.

Run:  py bench_chaos.py
"""

import math
import time

import sinai_billiard as sb


def cfg_of(board="circle", obstacle="none", ratio=1.5, size=1.0,
           ox=0.0, oy=0.0, orx=0.35, ory=0.25,
           r0=1.0, a1=0.0, b1=0.0, a2=0.0, b2=0.0, a3=0.0, b3=0.0,
           sx=0.5, sy=0.0):
    c = sb.Config()
    c.board_shape = board
    c.board_ratio = ratio
    c.board_size = size
    c.obstacle_shape = obstacle
    c.obstacle_x, c.obstacle_y = ox, oy
    c.obstacle_rx, c.obstacle_ry = orx, ory
    c.polar_r0, c.polar_a1, c.polar_b1 = r0, a1, b1
    c.polar_a2, c.polar_b2, c.polar_a3, c.polar_b3 = a2, b2, a3, b3
    c.start_x, c.start_y = sx, sy
    c.show_plot = False
    return c


def curvature_numerator(theta, cfg):
    """Sign of this decides local convexity of a polar boundary."""
    h = 1e-5
    r = sb.polar_radius(theta, cfg)
    d1 = sb.polar_radius_deriv(theta, cfg)
    d2 = (sb.polar_radius_deriv(theta + h, cfg)
          - sb.polar_radius_deriv(theta - h, cfg)) / (2 * h)
    return r * r + 2 * d1 * d1 - r * d2


def is_convex(cfg, samples=2000):
    worst = min(curvature_numerator(2 * math.pi * i / samples, cfg)
                for i in range(samples))
    return worst > 0, worst


# ---------------------------------------------------------------------------
# Benchmark cases: (name, expected, note, cfg)
# expected: "0" integrable, "1" fully chaotic, "mixed" both coexist
# ---------------------------------------------------------------------------
def build_cases():
    return [
        ("Circle", "0", "integrable: angular momentum conserved",
         cfg_of(board="circle", sx=0.5, sy=0.0)),

        ("Rectangle 3:2", "0", "integrable: separable, 2 conserved actions",
         cfg_of(board="rectangle", ratio=1.5, sx=0.5, sy=0.2)),

        ("Square", "0", "integrable: separable",
         cfg_of(board="rectangle", ratio=1.0, sx=0.5, sy=0.2)),

        ("Ellipse a/b=1.5", "0", "integrable: Joachimsthal invariant",
         cfg_of(board="ellipse", ratio=1.5, sx=0.2, sy=0.4)),

        ("Ellipse a/b=3.0", "0", "integrable: Joachimsthal invariant",
         cfg_of(board="ellipse", ratio=3.0, sx=0.2, sy=0.4)),

        ("Concentric annulus", "0",
         "integrable: centred scatterer keeps angular momentum",
         cfg_of(board="circle", obstacle="circle", orx=0.3,
                ox=0.0, oy=0.0, sx=0.65, sy=0.0)),

        ("Sinai billiard (square + centred disc)", "1",
         "Sinai 1970: dispersing scatterer, ergodic & K-mixing",
         cfg_of(board="rectangle", ratio=1.0, obstacle="circle", orx=0.3,
                sx=0.6, sy=0.55)),

        ("Sinai billiard (3:2 box + centred disc)", "1",
         "dispersing scatterer in a box",
         cfg_of(board="rectangle", ratio=1.5, obstacle="circle", orx=0.3,
                sx=0.9, sy=0.55)),

        ("Eccentric annulus", "mixed",
         "Bohigas et al 1993: whispering-gallery islands + chaotic sea",
         cfg_of(board="circle", obstacle="circle", orx=0.25,
                ox=0.35, oy=0.0, sx=-0.6, sy=0.35)),

        ("Ellipse + centred disc", "1",
         "dispersing scatterer destroys the ellipse invariant",
         cfg_of(board="ellipse", ratio=1.5, obstacle="circle", orx=0.3,
                sx=1.0, sy=0.4)),

        ("Limacon lambda=0.10", "0",
         "Robnik family: near-circle, KAM regular dominates",
         cfg_of(board="polar", r0=1.0, a1=0.10, sx=0.2, sy=0.1)),

        ("Limacon lambda=0.30", "mixed", "Robnik family: mixed phase space",
         cfg_of(board="polar", r0=1.0, a1=0.30, sx=0.2, sy=0.1)),

        ("Limacon lambda=0.60", "mixed",
         "Robnik family: chaos dominant, islands remain",
         cfg_of(board="polar", r0=1.0, a1=0.60, sx=0.2, sy=0.1)),

        ("Limacon lambda=0.90", "1",
         "Robnik family: approaching the ergodic cardioid",
         cfg_of(board="polar", r0=1.0, a1=0.90, sx=0.2, sy=0.1)),

        ("Near-cardioid lambda=0.99", "1",
         "Wojtkowski/Markarian: cardioid is ergodic & K-mixing",
         cfg_of(board="polar", r0=1.0, a1=0.99, sx=0.2, sy=0.1)),
    ]


def survey(cfg, n_trials, n_bounces):
    t0 = time.time()
    r = sb.measure_board_chaoticness(cfg, n_trials=n_trials,
                                     n_bounces=n_bounces, verbose=False)
    return r, time.time() - t0


def verdict(expected, frac):
    """Does the measured fraction agree with the literature expectation?"""
    if expected == "0":
        return "OK" if frac <= 0.02 else "MISMATCH"
    if expected == "1":
        return "OK" if frac >= 0.90 else "MISMATCH"
    return "OK" if 0.05 <= frac <= 0.95 else "MISMATCH"


def main():
    n_trials, n_bounces = 180, 400
    print("SALI chaos-checker benchmark  ({} angles x {} bounces)".format(
        n_trials, n_bounces))
    print("persist={}  threshold={:g}".format(
        sb.SALI_DEFAULT_PERSIST, sb.SALI_DEFAULT_THRESHOLD))
    print("")
    header = "{:<40} {:>8} {:>8} {:>7} {:>7} {:>9}".format(
        "billiard", "expect", "chaotic", "failed", "time", "verdict")
    print(header)
    print("-" * len(header))

    rows = []
    for name, expected, note, cfg in build_cases():
        try:
            sb.validate_start(cfg)
        except ValueError as e:
            print("{:<40} {:>8} {:>8} {:>7} {:>7} {:>9}".format(
                name, expected, "-", "-", "-", "REJECTED"))
            print("      cannot run: {}".format(e))
            rows.append((name, expected, None, note, "REJECTED"))
            continue
        r, dt = survey(cfg, n_trials, n_bounces)
        v = verdict(expected, r.chaotic_fraction)
        print("{:<40} {:>8} {:>8.3f} {:>7} {:>6.1f}s {:>9}".format(
            name, expected, r.chaotic_fraction, r.n_failed, dt, v))
        rows.append((name, expected, r.chaotic_fraction, note, v))

    print("")
    print("MISMATCHES vs literature")
    print("-" * 60)
    bad = [x for x in rows if x[4] != "OK"]
    if not bad:
        print("  none")
    for name, expected, frac, note, v in bad:
        got = "n/a" if frac is None else "{:.3f}".format(frac)
        print("  {:<40} expected {:<6} got {:<6} [{}]".format(
            name, expected, got, v))
        print("      {}".format(note))


if __name__ == "__main__":
    main()
