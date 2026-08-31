"""
Follow-up diagnostics for the SALI chaos-checker benchmark.

1) Can the proven-ergodic cardioid even be represented?
2) Where does the limacon boundary lose convexity?
3) Are the "regular" orbits in a scattered board exactly the ones that
   never reach the scatterer (whispering gallery)?
4) How much does the single-start-point sweep change the verdict?
"""

import math

import sinai_billiard as sb
from bench_chaos import cfg_of, is_convex


def section(title):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


def q1_cardioid():
    section("1) Exact cardioid r = 1 + cos(theta): proven ergodic. Representable?")
    for lam in (0.90, 0.99, 1.0, 1.10):
        cfg = cfg_of(board="polar", r0=1.0, a1=lam, sx=0.2, sy=0.1)
        rmin = sb.min_polar_radius(cfg)
        try:
            sb.validate_start(cfg)
            status = "accepted"
        except ValueError as e:
            status = "REJECTED: " + str(e).split("(")[0].strip()
        print("  lambda={:<5} min r(theta)={:+.4f}   {}".format(lam, rmin, status))


def q2_convexity():
    section("2) Limacon convexity (non-convex => dispersing => strong chaos)")
    prev = None
    for i in range(0, 21):
        lam = i / 20.0
        cfg = cfg_of(board="polar", r0=1.0, a1=lam)
        conv, worst = is_convex(cfg)
        if prev is not None and prev != conv:
            print("  --- convexity changes between lambda={:.2f} and {:.2f} ---"
                  .format(lam - 0.05, lam))
        prev = conv
        if i % 2 == 0 or not conv:
            print("  lambda={:<5} convex={:<5} min curvature numerator={:+.4f}"
                  .format(lam, str(conv), worst))


def classify_angle(cfg, ang, n_bounces=400):
    o = sb.compute_sali_for_angle(cfg, ang, n_bounces=n_bounces)
    return o.label


def obstacle_hits(cfg, ang, n_bounces=400):
    """How many times this orbit actually touches the scatterer."""
    x, y = cfg.start_x, cfg.start_y
    th = math.radians(ang)
    vx, vy = math.cos(th), math.sin(th)
    hits = 0
    for _ in range(n_bounces):
        board = sb.next_board_hit(x, y, vx, vy, cfg)
        obst = sb.next_obstacle_hit(x, y, vx, vy, cfg)
        pick = None
        if board is not None:
            pick = ("board",) + board
        if obst is not None and (pick is None or obst[0] < pick[1]):
            pick = ("obstacle",) + obst
        if pick is None:
            break
        what, t, nx, ny = pick
        if what == "obstacle":
            hits += 1
        x, y = x + t * vx, y + t * vy
        vx, vy = sb.reflect(vx, vy, nx, ny)
        x, y = x + 1e-9 * nx, y + 1e-9 * ny
    return hits


def q3_whispering(name, cfg, n_angles=180):
    print("\n  " + name)
    reg_never = reg_hit = ch_never = ch_hit = 0
    for i in range(n_angles):
        ang = 360.0 * i / n_angles
        lab = classify_angle(cfg, ang)
        h = obstacle_hits(cfg, ang)
        if lab == "regular":
            if h == 0:
                reg_never += 1
            else:
                reg_hit += 1
        elif lab == "chaotic":
            if h == 0:
                ch_never += 1
            else:
                ch_hit += 1
    print("    labelled REGULAR & never touches scatterer : {}".format(reg_never))
    print("    labelled REGULAR & does touch scatterer    : {}".format(reg_hit))
    print("    labelled CHAOTIC & never touches scatterer : {}".format(ch_never))
    print("    labelled CHAOTIC & does touch scatterer    : {}".format(ch_hit))


def q3():
    section("3) Are 'regular' orbits just the ones that miss the scatterer?")
    q3_whispering("Ellipse a/b=1.5 + centred disc r=0.3",
                  cfg_of(board="ellipse", ratio=1.5, obstacle="circle",
                         orx=0.3, sx=1.0, sy=0.4))
    q3_whispering("Eccentric annulus (disc r=0.25 at x=0.35)",
                  cfg_of(board="circle", obstacle="circle", orx=0.25,
                         ox=0.35, oy=0.0, sx=-0.6, sy=0.35))


def q4():
    section("4) Same board, different start point: does the score move?")
    boards = [
        ("Sinai (square + centred disc)   [ergodic]",
         dict(board="rectangle", ratio=1.0, obstacle="circle", orx=0.3),
         [(0.6, 0.55), (0.9, 0.1), (-0.5, -0.7), (0.0, 0.8), (0.45, 0.45)]),
        ("Eccentric annulus               [mixed]",
         dict(board="circle", obstacle="circle", orx=0.25, ox=0.35, oy=0.0),
         [(-0.6, 0.35), (0.0, 0.95), (-0.95, 0.0), (0.0, 0.5), (-0.3, 0.1)]),
        ("Ellipse + centred disc          [mixed]",
         dict(board="ellipse", ratio=1.5, obstacle="circle", orx=0.3),
         [(1.0, 0.4), (0.0, 0.95), (1.4, 0.05), (0.5, 0.6), (0.4, 0.4)]),
        ("Limacon lambda=0.30             [mixed]",
         dict(board="polar", r0=1.0, a1=0.30),
         [(0.2, 0.1), (0.6, 0.3), (-0.4, 0.2), (0.0, 0.7), (0.9, 0.0)]),
    ]
    for name, kw, starts in boards:
        vals = []
        for (sx, sy) in starts:
            cfg = cfg_of(sx=sx, sy=sy, **kw)
            try:
                sb.validate_start(cfg)
            except ValueError:
                continue
            r = sb.measure_board_chaoticness(cfg, n_trials=120, n_bounces=300,
                                             verbose=False)
            vals.append(((sx, sy), r.chaotic_fraction))
        if not vals:
            continue
        fr = [v for _, v in vals]
        print("\n  {}".format(name))
        for (p, v) in vals:
            print("    start=({:+.2f},{:+.2f}) -> {:.3f}".format(p[0], p[1], v))
        print("    spread: min={:.3f} max={:.3f}  SWING={:.3f}".format(
            min(fr), max(fr), max(fr) - min(fr)))


if __name__ == "__main__":
    q1_cardioid()
    q2_convexity()
    q3()
    q4()
