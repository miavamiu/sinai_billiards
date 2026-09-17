"""
Benchmark the Lyapunov number checker against values known from literature
and against exactly solvable periodic orbits.

Run:  py bench_lyapunov.py

REFERENCES USED
---------------
[D97] P. Dahlqvist, "The Lyapunov exponent in the Sinai billiard in the small
      scatterer limit", Nonlinearity 10 (1997) 119; arXiv:chao-dyn/9601007.
      Disk of radius R centred in a UNIT square (equivalently the periodic
      Lorentz gas on the unit lattice), DISK-TO-DISK map:
          lambda = -2 log R + C + O(R log^2 R),
          C = 1 - 4 log 2 + 27 zeta(3) / (2 pi^2)  = -0.12837205

[BZ03] F. Boca, A. Zaharescu, arXiv:math/0301270, quoting Dahlqvist's
      conjecture for the KS entropy of the SAME billiard map:
          h(T) = -2 log eps + 2 - 3 log 2 + 9 zeta(3) / (4 zeta(2)) + o(1)
                = -2 log eps + 1.5651 + o(1)
      By Pesin's identity h = lambda for this map, so [D97] and [BZ03] should
      agree - but their constants differ by exactly 1 + log 2 = 1.6931.
      This benchmark measures which one the simulation supports.

[BD97] A. Baecker, H. R. Dullin, "Symbolic dynamics and periodic orbits for the
      cardioid billiard", J. Phys. A 30 (1997) 1991, eqs. (58)-(59).
      Cardioid r(theta) = 1 + cos(theta):
          mean length between reflections  <l>  = 1.851  (= 3 pi^2 / 16)
          KS entropy per collision         h_KS = 0.653
      Analytic Wojtkowski lower bound in the same paper: 0.633.

[OTOC] arXiv:2408.04052, Table 1: cardioid classical Lyapunov exponent per
      collision = 0.6649.

[CB] P. Cvitanovic et al., ChaosBook: the fundamental two-disk periodic orbit
      (disk radius a, centre separation R) has the EXACT stability multiplier
          Lambda = R/a - 1 + (R/a) sqrt(1 - 2a/R).
      A disk plus a flat wall unfolds to this by mirror symmetry, which is a
      geometry this simulator can build exactly.

[BS78] G. Benettin, J.-M. Strelcyn, Phys. Rev. A 17 (1978) 773: Bunimovich
      stadium, max Lyapunov exponent ~0.43 at a/r = 1. NOT tested here - this
      simulator has no stadium shape (rectangle/circle/ellipse/polar only).
"""

import math
import time

import sinai_billiard as sb


# ---------------------------------------------------------------------------
# Reference constants
# ---------------------------------------------------------------------------

ZETA3 = 1.2020569031595942854
ZETA2 = math.pi * math.pi / 6.0

# [D97] eq. (75)
C_DAHLQVIST = 1.0 - 4.0 * math.log(2.0) + 27.0 * ZETA3 / (2.0 * math.pi ** 2)
# [BZ03] constant term for the KS entropy of the same map
C_BOCA_ZAHARESCU = 2.0 - 3.0 * math.log(2.0) + 9.0 * ZETA3 / (4.0 * ZETA2)

CARDIOID_HKS_BD97 = 0.653          # [BD97] eq. (59)
CARDIOID_HKS_OTOC = 0.6649         # [OTOC] Table 1
CARDIOID_MEAN_LENGTH = 3.0 * math.pi ** 2 / 16.0   # [BD97] eq. (61) = 1.8506


def section(title):
    print()
    print("=" * 74)
    print("  " + title)
    print("=" * 74)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rect_disk_cfg(half_width, disk_r, half_height=1.0):
    c = sb.Config()
    c.board_shape = "rectangle"
    c.board_size = half_height
    c.board_ratio = half_width / half_height
    c.obstacle_shape = "circle"
    c.obstacle_rx = disk_r
    c.obstacle_x = c.obstacle_y = 0.0
    c.show_plot = False
    return c


def cardioid_cfg():
    c = sb.Config()
    c.board_shape = "polar"
    c.polar_r0 = 1.0
    c.polar_a1 = 1.0
    c.polar_b1 = c.polar_a2 = c.polar_b2 = c.polar_a3 = c.polar_b3 = 0.0
    c.obstacle_shape = "none"
    c.show_plot = False
    return c


def surface_split(cfg, angle_deg, n_bounces):
    """
    Walk the same orbit the Lyapunov checker walks and count how many
    collisions land on the obstacle vs the board walls.

    Needed because published Sinai-billiard exponents are quoted PER DISK
    COLLISION, while the checker averages over EVERY collision.
    """
    x, y = float(cfg.start_x), float(cfg.start_y)
    th = math.radians(float(angle_deg))
    vx, vy = math.cos(th), math.sin(th)
    nudge = max(cfg.epsilon, 1e-8)
    n_obst = 0
    n_total = 0
    for _ in range(int(n_bounces)):
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
        n_total += 1
        if what == "obstacle":
            n_obst += 1
        x, y = x + t * vx, y + t * vy
        vx, vy = sb.reflect(vx, vy, nx, ny)
        x, y = x + nudge * nx, y + nudge * ny
    return n_obst, n_total


def orbit_grid(cfg, n_starts, n_angles, seed=2024):
    """Start points uniform by area, angles on an off-axis grid."""
    points = sb.sample_interior_points(cfg, n_starts, seed=seed)
    step = 360.0 / n_angles
    angles = [step * (i + 0.37) for i in range(n_angles)]
    return points, angles


def mean_lyapunov(cfg, n_starts, n_angles, n_bounces, per_disk=False,
                  seed=2024):
    """
    Phase-space average of the per-collision Lyapunov exponent.

    per_disk=True rescales each orbit by n_total / n_obstacle_hits, converting
    "per collision" into "per disk collision" so it can be compared with the
    published Sinai-billiard values.
    """
    points, angles = orbit_grid(cfg, n_starts, n_angles, seed=seed)
    probe = sb.Config(**cfg.__dict__)
    lams = []
    hit_fracs = []
    for (sx, sy) in points:
        probe.start_x, probe.start_y = sx, sy
        for ang in angles:
            r = sb.compute_lyapunov_for_angle(probe, ang, n_bounces=n_bounces)
            if r.label == "failed":
                continue
            if not per_disk:
                lams.append(r.exponent)
                continue
            n_obst, n_total = surface_split(probe, ang, r.n_bounces_done)
            if n_obst < 20:
                continue
            hit_fracs.append(n_obst / float(n_total))
            lams.append(r.exponent * n_total / float(n_obst))
    if not lams:
        return float("nan"), float("nan"), 0, float("nan")
    mean = sum(lams) / len(lams)
    var = sum((v - mean) ** 2 for v in lams) / max(1, len(lams) - 1)
    sem = math.sqrt(var / len(lams))
    frac = (sum(hit_fracs) / len(hit_fracs)) if hit_fracs else float("nan")
    return mean, sem, len(lams), frac


def mean_segment_length(cfg, n_bounces=4000, angle=35.0):
    probe = sb.Config(**cfg.__dict__)
    probe.start_angle_deg = angle
    probe.max_bounces = n_bounces
    probe.max_distance = 1e12
    probe.show_plot = False
    res = sb.run_trial(probe, trial_id=1)
    if res.total_bounces == 0:
        return float("nan")
    return res.total_distance / res.total_bounces


# ---------------------------------------------------------------------------
# 1. Integrable boards: lambda must be 0
# ---------------------------------------------------------------------------

def test_integrable():
    section("1. INTEGRABLE BOARDS - exact reference lambda = 0")
    print("Circle, ellipse and rectangle are integrable, so the true")
    print("per-collision Lyapunov exponent is EXACTLY 0. A finite-time")
    print("estimate cannot be 0: deviation vectors grow LINEARLY, so")
    print("lambda_n ~ log(n)/n. The table checks that scaling.")
    print()

    cases = []
    c = sb.Config(); c.board_shape = "circle"; c.obstacle_shape = "none"
    c.start_x, c.start_y, c.start_angle_deg = 0.5, 0.0, 35.0
    c.show_plot = False
    cases.append(("circle", c))

    e = sb.Config(); e.board_shape = "ellipse"; e.obstacle_shape = "none"
    e.board_ratio = 1.5
    e.start_x, e.start_y, e.start_angle_deg = 0.5, 0.1, 35.0
    e.show_plot = False
    cases.append(("ellipse r=1.5", e))

    r = sb.Config(); r.board_shape = "rectangle"; r.obstacle_shape = "none"
    r.board_ratio = 1.5
    r.start_x, r.start_y, r.start_angle_deg = 0.5, 0.1, 35.0
    r.show_plot = False
    cases.append(("rectangle r=1.5", r))

    print("board\tn_bounces\tlambda\tL\tlabel\tlambda*n/log(n)")
    for name, cfg in cases:
        for n in (100, 250, 500, 1000, 2000):
            o = sb.compute_lyapunov_for_angle(cfg, cfg.start_angle_deg,
                                              n_bounces=n)
            scaled = o.exponent * n / math.log(n)
            print("{}\t{}\t{:.6f}\t{:.5f}\t{}\t{:.3f}".format(
                name, n, o.exponent, o.number, o.label, scaled))
        print()

    print("INCONSISTENCY WATCH: the label uses a FIXED cutoff")
    print("  LYAPUNOV_REGULAR_THRESHOLD = {:g}".format(
        sb.LYAPUNOV_REGULAR_THRESHOLD))
    print("but log(n)/n crosses that cutoff at low n:")
    for n in (50, 100, 200, 500, 1000):
        print("  n={:<5} log(n)/n = {:.4f}   {}".format(
            n, math.log(n) / n,
            "ABOVE cutoff -> regular board can be mislabelled chaotic"
            if math.log(n) / n > sb.LYAPUNOV_REGULAR_THRESHOLD else "ok"))


# ---------------------------------------------------------------------------
# 2. Exactly solvable periodic orbits
# ---------------------------------------------------------------------------

def exact_two_disk_multiplier(a, sep):
    """[CB] Lambda = R/a - 1 + (R/a) sqrt(1 - 2a/R)."""
    q = sep / a
    return q - 1.0 + q * math.sqrt(1.0 - 2.0 * a / sep)


def test_periodic_orbits():
    section("2. EXACT PERIODIC ORBIT - disk + flat wall (unfolds to two disks)")
    print("Ball on the axis bouncing perpendicular between a centred disk of")
    print("radius a and the flat right wall at distance hw. Mirroring the wall")
    print("turns this into the two-disk orbit of [CB] with centre separation")
    print("R = 2*hw, whose multiplier Lambda is known in closed form.")
    print("One period = 2 collisions (disk + wall), so lambda = log(Lambda)/2.")
    print()
    print("a\thw\tLambda_exact\tlambda_exact\tlambda_measured\trel_err")

    cases = ((0.35, 1.5), (0.5, 1.0), (0.2, 1.0), (0.8, 1.2), (0.15, 0.8))
    for a, hw in cases:
        cfg = rect_disk_cfg(hw, a)
        cfg.start_x, cfg.start_y = (a + hw) / 2.0, 0.0
        cfg.start_angle_deg = 0.0
        lam_exact = math.log(exact_two_disk_multiplier(a, 2.0 * hw)) / 2.0
        # n = 15 -> burn-in 5 -> 10 counted steps (EVEN, see note below)
        o = sb.compute_lyapunov_for_angle(cfg, 0.0, n_bounces=15)
        rel = abs(o.exponent - lam_exact) / lam_exact
        print("{}\t{}\t{:.6f}\t{:.8f}\t{:.8f}\t{:.1e}".format(
            a, hw, exact_two_disk_multiplier(a, 2.0 * hw),
            lam_exact, o.exponent, rel))

    print()
    print("Determinant check. The billiard map is symplectic in BIRKHOFF")
    print("coordinates (arc length, sin of the incidence angle), but the")
    print("checker works in (tangent displacement, angle). In that chart")
    print("det J is NOT 1 per step - it carries a cos-angle metric factor.")
    print("What must hold is that those factors TELESCOPE, so that the mean")
    print("of log|det J| per collision goes to 0 and lambda is unaffected.")
    cfg = rect_disk_cfg(1.5, 0.35)
    cfg.start_x, cfg.start_y, cfg.start_angle_deg = 0.9, 0.0, 37.0
    x, y = cfg.start_x, cfg.start_y
    th = math.radians(cfg.start_angle_deg)
    x, y, th, nx, ny = sb._bounce_map_state(x, y, th, cfg)
    dets = []
    log_sum = 0.0
    for _ in range(2000):
        got = sb._finite_diff_jacobian_2d(x, y, th, nx, ny, cfg)
        if got is None:
            break
        x, y, th, nx, ny, J = got
        det = J[0][0] * J[1][1] - J[0][1] * J[1][0]
        dets.append(det)
        log_sum += math.log(abs(det))
    print("  collisions            = {}".format(len(dets)))
    print("  det J range           = {:.4f} .. {:.4f}".format(
        min(dets), max(dets)))
    print("  telescoped product    = {:.6f}   (bounded, not growing)".format(
        math.exp(log_sum)))
    print("  mean log|det J|/coll  = {:+.2e}  (-> 0, so lambda is clean)"
          .format(log_sum / len(dets)))

    print()
    print("INCONSISTENCY WATCH: odd vs even number of averaged steps.")
    print("This orbit has period 2, so the two collisions contribute very")
    print("different stretches. Averaging an ODD number of steps keeps one")
    print("extra copy of one of them and biases lambda badly.")
    print()
    print("n_bounces\tcounted\tlambda\texact\trel_err")
    cfg = rect_disk_cfg(1.5, 0.35)
    cfg.start_x, cfg.start_y, cfg.start_angle_deg = (0.35 + 1.5) / 2.0, 0.0, 0.0
    lam_exact = math.log(exact_two_disk_multiplier(0.35, 3.0)) / 2.0
    for n in (6, 7, 10, 11, 14, 15, 20, 21):
        burn = min(50, max(5, n // 10))
        o = sb.compute_lyapunov_for_angle(cfg, 0.0, n_bounces=n)
        counted = n - burn
        print("{}\t{} ({})\t{:.6f}\t{:.6f}\t{:.1e}".format(
            n, counted, "even" if counted % 2 == 0 else "ODD",
            o.exponent, lam_exact,
            abs(o.exponent - lam_exact) / lam_exact))

    print()
    print("INCONSISTENCY WATCH: roundoff drift off an UNSTABLE periodic orbit.")
    print("lambda = {:.4f} means the orbit leaves the periodic solution once"
          .format(lam_exact))
    print("1e-16 * exp(lambda*n) ~ 1, i.e. around n ~ {:.0f} collisions."
          .format(math.log(1e16) / lam_exact))
    print("Past that the checker measures the surrounding chaotic sea instead.")
    print()
    print("n_bounces\tlambda\texact\tnote")
    for n in (15, 25, 31, 51, 101, 501):
        o = sb.compute_lyapunov_for_angle(cfg, 0.0, n_bounces=n)
        note = "on orbit" if abs(o.exponent - lam_exact) < 1e-3 else "DRIFTED"
        print("{}\t{:.6f}\t{:.6f}\t{}".format(n, o.exponent, lam_exact, note))


# ---------------------------------------------------------------------------
# 3. Cardioid: published KS entropy per collision
# ---------------------------------------------------------------------------

def test_cardioid(n_starts=6, n_angles=15, n_bounces=800):
    section("3. CARDIOID r = 1 + cos(theta) - published h_KS per collision")
    print("[BD97] eq. (59): h_KS = {:.3f} per collision".format(
        CARDIOID_HKS_BD97))
    print("[OTOC] Table 1 : lambda = {:.4f} per collision".format(
        CARDIOID_HKS_OTOC))
    print("[BD97] eq. (61): <l> = 3 pi^2 / 16 = {:.4f}  (geometry check)"
          .format(CARDIOID_MEAN_LENGTH))
    print()

    cfg = cardioid_cfg()

    t0 = time.time()
    seg = mean_segment_length(cfg, n_bounces=4000)
    print("geometry check: measured <l> = {:.4f}  vs  {:.4f}  (rel err {:.2%})"
          .format(seg, CARDIOID_MEAN_LENGTH,
                  abs(seg - CARDIOID_MEAN_LENGTH) / CARDIOID_MEAN_LENGTH))
    print()

    print("n_bounces\torbits\tlambda_mean\tsem\tvs BD97\tvs OTOC")
    for nb in (200, 400, n_bounces):
        mean, sem, n_ok, _ = mean_lyapunov(cfg, n_starts, n_angles, nb)
        print("{}\t{}\t{:.4f}\t{:.4f}\t{:+.2%}\t{:+.2%}".format(
            nb, n_ok, mean, sem,
            (mean - CARDIOID_HKS_BD97) / CARDIOID_HKS_BD97,
            (mean - CARDIOID_HKS_OTOC) / CARDIOID_HKS_OTOC))
    print("  ({:.1f} s)".format(time.time() - t0))


# ---------------------------------------------------------------------------
# 4. Sinai billiard: Dahlqvist's small-scatterer law
# ---------------------------------------------------------------------------

def test_sinai(n_starts=5, n_angles=12, n_bounces=3000):
    section("4. SINAI BILLIARD - Dahlqvist small-scatterer law")
    print("Square box with reflecting walls + centred disk unfolds to the")
    print("periodic Lorentz gas on a lattice of spacing = box side, so the")
    print("scaled radius is  R = disk_radius / box_side.")
    print()
    print("[D97]  lambda_per_disk = -2 log R + C,  C = {:+.8f}".format(
        C_DAHLQVIST))
    print("[BZ03] same map, KS entropy constant = {:+.6f}".format(
        C_BOCA_ZAHARESCU))
    print("       the two differ by 1 + log 2 = {:.6f}".format(
        1.0 + math.log(2.0)))
    print()
    print("The checker averages over ALL collisions, but the published law is")
    print("PER DISK COLLISION, so each orbit is rescaled by n_total/n_disk.")
    print()

    t0 = time.time()
    rows = []
    print("R\tdisk_frac\tlam_all_coll\tlam_per_disk\tsem\t-2logR+C_D97\tresidual")
    for R in (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40):
        # box side = 2*board_size = 2 -> disk radius = 2R
        cfg = rect_disk_cfg(1.0, 2.0 * R, half_height=1.0)
        lam_all, _, _, _ = mean_lyapunov(cfg, n_starts, n_angles, n_bounces)
        lam_disk, sem, n_ok, frac = mean_lyapunov(
            cfg, n_starts, n_angles, n_bounces, per_disk=True)
        pred = -2.0 * math.log(R) + C_DAHLQVIST
        rows.append((R, lam_disk))
        print("{:.2f}\t{:.3f}\t{:.4f}\t{:.4f}\t{:.4f}\t{:.4f}\t{:+.4f}".format(
            R, frac, lam_all, lam_disk, sem, pred, lam_disk - pred))
    print("  ({:.1f} s)".format(time.time() - t0))

    # Fit lambda = slope * log(R) + intercept
    xs = [math.log(R) for R, _ in rows]
    ys = [lam for _, lam in rows]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    print()
    print("least-squares fit  lambda_per_disk = slope*log(R) + intercept")
    print("  slope     = {:+.4f}   (theory: -2)".format(slope))
    print("  intercept = {:+.4f}   ([D97] C = {:+.4f}, [BZ03] = {:+.4f})"
          .format(intercept, C_DAHLQVIST, C_BOCA_ZAHARESCU))
    print()
    print("Reminder: [D97] holds as R -> 0 with error O(R log^2 R), which is")
    print("still O(0.5) over this whole R range, so only the SLOPE is a sharp")
    print("test; the intercept is indicative.")


def main():
    print("LYAPUNOV CHECKER BENCHMARK vs LITERATURE")
    print("sinai_billiard.LYAPUNOV_DEFAULT_BOUNCES     = {}".format(
        sb.LYAPUNOV_DEFAULT_BOUNCES))
    print("sinai_billiard.LYAPUNOV_REGULAR_THRESHOLD   = {}".format(
        sb.LYAPUNOV_REGULAR_THRESHOLD))
    test_integrable()
    test_periodic_orbits()
    test_cardioid()
    test_sinai()
    section("NOT TESTED")
    print("[BS78] Bunimovich stadium (max lambda ~0.43 at a/r = 1): this")
    print("simulator has no stadium boundary, and a polar curve cannot")
    print("reproduce one, so the case is out of reach here.")
    print("[OTOC] 'Sinai' lambda = 0.8048 with d_avg = 0.4817 at area 1: the")
    print("paper does not pin down the box/disk geometry precisely enough to")
    print("rebuild it, so it is quoted but not tested.")


if __name__ == "__main__":
    main()
