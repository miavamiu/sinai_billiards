"""
Pilot for the "deform an integrable board" study.

Two arms, same unperturbed board (the unit circle), two different KINDS of
deformation:

  ARM A  smooth convex bump   r(theta) = 1 + eps*cos(theta)   (Robnik limacon)
  ARM B  curvature break      stadium, straight section of half-length a

Arm A keeps the boundary smooth, so Lazutkin's theorem guarantees caustics
near the wall and therefore a surviving regular region. Arm B breaks the
curvature, which removes that guarantee. The pilot checks whether the two
arms have visibly different onsets of chaos at matched deformation size.
"""

import math
import sys
import time

import sinai_billiard as sb

N_ANGLES = 24
N_BOUNCES = 300


def limacon(eps):
    c = sb.Config()
    c.board_shape = "polar"
    c.polar_r0 = 1.0
    c.polar_a1 = eps
    c.obstacle_shape = "none"
    c.show_plot = False
    c.start_x, c.start_y = 0.25, 0.15
    return c


def stadium(a):
    c = sb.Config()
    c.board_shape = "stadium"
    c.board_size = 1.0
    c.stadium_half_length = a
    c.stadium_curve = 1.0
    c.obstacle_shape = "none"
    c.show_plot = False
    c.start_x, c.start_y = 0.15, 0.25
    return c


def min_curvature(eps, n=4000):
    """
    Smallest curvature of r(theta) = 1 + eps*cos(theta).

    Polar curvature: (r^2 + 2 r'^2 - r r'') / (r^2 + r'^2)^{3/2}.
    It first reaches 0 at theta = pi, where the numerator is
    (1-eps)(1-2eps) - so the boundary stops being convex at eps = 1/2.
    """
    best = float("inf")
    for i in range(n):
        th = 2.0 * math.pi * i / n
        r = 1.0 + eps * math.cos(th)
        rp = -eps * math.sin(th)
        rpp = -eps * math.cos(th)
        num = r * r + 2.0 * rp * rp - r * rpp
        best = min(best, num / (r * r + rp * rp) ** 1.5)
    return best


def row(label, cfg, extra=""):
    t0 = time.time()
    p = sb.analyse_chaos(cfg, n_angles=N_ANGLES, n_bounces=N_BOUNCES, verbose=False)
    lam = p.lyap_exponent
    lam_s = "  -   " if lam != lam else "{:.4f}".format(lam)
    print("{:<8} {:<14} {:<7.3f} {:<8} {:<18} {:.0f}s".format(
        label, extra, p.chaotic_fraction, lam_s, p.band, time.time() - t0))
    sys.stdout.flush()


print("ARM A: smooth deformation of the circle, limacon r = 1 + eps cos(theta)")
print("{:<8} {:<14} {:<7} {:<8} {:<18}".format(
    "eps", "min curv", "frac", "lambda", "band"))
sys.stdout.flush()
for eps in (0.01, 0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0):
    row("{:.3f}".format(eps), limacon(eps),
        "{:+.4f}".format(min_curvature(eps)))

print()
print("ARM B: same circle deformed with a CURVATURE BREAK (stadium)")
print("{:<8} {:<14} {:<7} {:<8} {:<18}".format(
    "a", "", "frac", "lambda", "band"))
sys.stdout.flush()
for a in (0.01, 0.05, 0.1, 0.2, 0.5, 1.0):
    row("{:.3f}".format(a), stadium(a))
