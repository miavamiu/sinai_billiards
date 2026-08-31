"""Check that the cardioid board is now usable and behaves as the literature says."""

import math

import sinai_billiard as sb
from bench_chaos import cfg_of

print("--- is the cardioid r = 1 + cos(theta) accepted? ---")
for lam in (0.99, 1.0, 1.0001, 1.1):
    cfg = cfg_of(board="polar", r0=1.0, a1=lam, sx=0.5, sy=0.1)
    try:
        sb.validate_start(cfg)
        status = "accepted"
    except ValueError as err:
        status = "rejected: " + str(err)[:44]
    print("  a1={:<8} min r={:+.6f}   {}".format(
        lam, sb.min_polar_radius(cfg), status))

cardioid = cfg_of(board="polar", r0=1.0, a1=1.0, sx=0.5, sy=0.1)
smooth = cfg_of(board="polar", r0=1.0, a1=0.3, sx=0.5, sy=0.1)
print()
print("origin is a boundary cusp on the cardioid -> inside? {}"
      .format(sb.point_inside_board(0.0, 0.0, cardioid)))
print("origin is interior on a smooth polar board -> inside? {}"
      .format(sb.point_inside_board(0.0, 0.0, smooth)))

print()
print("--- does a trial run and stay inside the cardioid? ---")
run = cfg_of(board="polar", r0=1.0, a1=1.0, sx=0.5, sy=0.1)
run.obstacle_shape = "none"
run.max_bounces = 300
run.show_plot = False
res = sb.run_trial(run, trial_id=1)
worst = 0.0
for x, y in zip(res.path_x, res.path_y):
    rho = math.hypot(x, y)
    if rho < 1e-12:
        continue
    worst = max(worst, rho - sb.polar_radius(math.atan2(y, x), run))
print("  bounces={}  max overshoot past the wall = {:.2e}".format(
    len(res.bounces), worst))

print()
print("--- chaoticness: the cardioid is PROVEN ergodic, expect ~1.000 ---")
for name, lam in (("limacon 0.90", 0.90), ("near-cardioid 0.99", 0.99),
                  ("CARDIOID 1.00", 1.00)):
    cfg = cfg_of(board="polar", r0=1.0, a1=lam, sx=0.5, sy=0.1)
    cfg.obstacle_shape = "none"
    r = sb.measure_board_chaoticness(cfg, n_trials=180, n_bounces=400,
                                     verbose=False)
    print("  {:<20} chaotic={:.3f}  regular={:.3f}  failed={}".format(
        name, r.chaotic_fraction, r.regular_fraction, r.n_failed))

print()
print("--- board-level score over start points sampled by area ---")
cfg = cfg_of(board="polar", r0=1.0, a1=1.0)
cfg.obstacle_shape = "none"
multi = sb.measure_board_chaos(cfg, n_starts=6, n_angles=90,
                               n_bounces=250, verbose=False)
print("  mean={:.3f}  min={:.3f}  max={:.3f}  spread={:.3f}".format(
    multi.mean_fraction, multi.min_fraction, multi.max_fraction, multi.spread))
