"""
Does the START POSITION matter on an EMPTY board (no obstacle)?

Part A: spread of the chaoticness score over start points sampled by area.
Part B: are hand-named positions (centre, corner, near-wall) typical, or are
        they special points that bias the answer?
"""

import math

import sinai_billiard as sb
from bench_chaos import cfg_of

N_STARTS, N_ANGLES, N_BOUNCES = 8, 60, 200


def empty(**kw):
    c = cfg_of(**kw)
    c.obstacle_shape = "none"
    return c


BOARDS = [
    ("Circle", empty(board="circle")),
    ("Rectangle 3:2", empty(board="rectangle", ratio=1.5)),
    ("Ellipse a/b=1.5", empty(board="ellipse", ratio=1.5)),
    ("Limacon 0.20 (transition)", empty(board="polar", r0=1.0, a1=0.20)),
    ("Limacon 0.30 (transition)", empty(board="polar", r0=1.0, a1=0.30)),
    ("Limacon 0.40 (transition)", empty(board="polar", r0=1.0, a1=0.40)),
    ("Cardioid 1.00", empty(board="polar", r0=1.0, a1=1.00)),
]


def pull_inside(cfg, x, y):
    """Shrink (x, y) toward the origin until it is a legal start, or give up."""
    for _ in range(60):
        if sb.point_inside_board(x, y, cfg) and not sb.point_inside_obstacle(x, y, cfg):
            return x, y
        x, y = x * 0.9, y * 0.9
        if abs(x) < 1e-6 and abs(y) < 1e-6:
            break
    return None


def score_at(cfg, sx, sy):
    probe = sb.copy.deepcopy(cfg)
    probe.start_x, probe.start_y = sx, sy
    r = sb.measure_board_chaoticness(probe, n_trials=N_ANGLES,
                                     n_bounces=N_BOUNCES, verbose=False)
    return r.chaotic_fraction


def part_a():
    print("=" * 78)
    print("A) Score spread over {} start points sampled uniformly BY AREA"
          .format(N_STARTS))
    print("   ({} angles x {} bounces per start)".format(N_ANGLES, N_BOUNCES))
    print("=" * 78)
    print("{:<28} {:>7} {:>7} {:>7} {:>8}  {}".format(
        "empty board", "mean", "min", "max", "+/-", "does start matter?"))
    out = {}
    for name, cfg in BOARDS:
        m = sb.measure_board_chaos(
            cfg, n_starts=N_STARTS, n_angles=N_ANGLES, n_bounces=N_BOUNCES,
            verbose=False)
        verdict = "NO - irrelevant" if not m.is_mixed else "YES - strongly"
        print("{:<28} {:>7.3f} {:>7.3f} {:>7.3f} {:>8.3f}  {}".format(
            name, m.mean_fraction, m.min_fraction, m.max_fraction,
            m.spread, verdict))
        out[name] = m
    return out


def part_b(multi):
    print("")
    print("=" * 78)
    print("B) Are NAMED positions typical, or special points that bias things?")
    print("=" * 78)
    for name, cfg in BOARDS:
        m = multi[name]
        if not m.is_mixed:
            continue  # nothing to bias on a uniform board
        hw, hh = sb.board_world_half_size(cfg)
        named = [
            ("centre", 0.0, 0.0),
            ("left-down corner", -0.9 * hw, -0.9 * hh),
            ("right-up corner", 0.9 * hw, 0.9 * hh),
            ("near wall (+x)", 0.9 * hw, 0.0),
            ("on vertical axis", 0.0, 0.9 * hh),
        ]
        print("")
        print("  {}   (area-sampled range {:.3f}-{:.3f}, mean {:.3f})".format(
            name, m.min_fraction, m.max_fraction, m.mean_fraction))
        for label, x, y in named:
            spot = pull_inside(cfg, x, y)
            if spot is None:
                print("    {:<18} no legal position".format(label))
                continue
            sx, sy = spot
            v = score_at(cfg, sx, sy)
            outside = v < m.min_fraction - 1e-9 or v > m.max_fraction + 1e-9
            flag = "  <-- OUTSIDE the typical range" if outside else ""
            print("    {:<18} ({:+.3f},{:+.3f}) -> {:.3f}{}".format(
                label, sx, sy, v, flag))


if __name__ == "__main__":
    multi = part_a()
    part_b(multi)
