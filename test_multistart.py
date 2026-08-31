"""Check the golden-angle start spread and the multi-start trial."""

import math

import sinai_billiard as sb
from bench_chaos import cfg_of

BOARDS = [
    ("rectangle 3:2", cfg_of(board="rectangle", ratio=1.5)),
    ("circle", cfg_of(board="circle")),
    ("ellipse a/b=3", cfg_of(board="ellipse", ratio=3.0)),
    ("limacon 0.30", cfg_of(board="polar", r0=1.0, a1=0.30)),
    ("cardioid 1.00", cfg_of(board="polar", r0=1.0, a1=1.00)),
]

print("1) wall distance helper agrees with the known geometry")
circ = cfg_of(board="circle", size=1.0)
ell = cfg_of(board="ellipse", ratio=3.0, size=1.0)
card = cfg_of(board="polar", r0=1.0, a1=1.0)
print("   circle, any direction      : {:.9f} (exact 1.0)".format(
    sb.boundary_distance(circ, 0.7)))
print("   ellipse along +x           : {:.9f} (exact 3.0)".format(
    sb.boundary_distance(ell, 0.0)))
print("   ellipse along +y           : {:.9f} (exact 1.0)".format(
    sb.boundary_distance(ell, math.pi / 2)))
print("   cardioid along +x          : {:.9f} (exact 2.0)".format(
    sb.boundary_distance(card, 0.0)))
print("   cardioid along the cusp    : {:.9f} (exact 0.0, no free space)".format(
    sb.boundary_distance(card, math.pi)))

print()
print("2) start points: all legal, none on a symmetry axis, spread by area")
for name, cfg in BOARDS:
    cfg.obstacle_shape = "none"
    pts = sb.spread_start_points(cfg, 5)
    hw, hh = sb.board_world_half_size(cfg)
    print("   {}".format(name))
    for (x, y) in pts:
        ang = math.degrees(math.atan2(y, x)) % 360.0
        reach = sb.boundary_distance(cfg, math.atan2(y, x))
        frac = math.hypot(x, y) / reach if reach > 0 else float("nan")
        near_axis = min(abs(ang - a) for a in (0, 45, 90, 135, 180, 225, 270, 315, 360))
        legal = sb.point_inside_board(x, y, cfg)
        print("     ({:+.3f},{:+.3f}) angle={:6.1f} deg  {:.0f}% to wall  "
              "axis gap={:4.1f} deg  inside={}".format(
                  x, y, ang, 100 * frac, near_axis, legal))
    assert all(sb.point_inside_board(x, y, cfg) for x, y in pts)

print()
print("3) multi-start trial runs on every board shape")
for name, cfg in BOARDS:
    cfg.obstacle_shape = "none"
    cfg.max_bounces = 60
    cfg.show_plot = False
    res = sb.run_multi_start_trial(cfg, n_points=5, verbose=False)
    print("   {:<16} {} paths, bounces {}".format(
        name, len(res), [r.total_bounces for r in res]))

print()
print("4) with an obstacle, starts inside the scatterer are avoided")
cfg = cfg_of(board="circle", obstacle="circle", orx=0.55)
cfg.max_bounces = 40
cfg.show_plot = False
pts = sb.spread_start_points(cfg, 6)
print("   obstacle radius 0.55, board radius 1.0 -> {} of 6 points usable".format(
    len(pts)))
for (x, y) in pts:
    assert not sb.point_inside_obstacle(x, y, cfg)
print("   none of them fall inside the obstacle: OK")

print()
print("5) does the overlay actually show different behaviour? (transition band)")
cfg = cfg_of(board="polar", r0=1.0, a1=0.30)
cfg.obstacle_shape = "none"
cfg.max_bounces = 200
cfg.show_plot = False
cfg.start_angle_deg = 35.0
res = sb.run_multi_start_trial(cfg, n_points=5, verbose=False)
for r in res:
    print("   start ({:+.3f},{:+.3f}) -> {} bounces, mean segment {:.4f}".format(
        r.cfg_snapshot["start_x"], r.cfg_snapshot["start_y"],
        r.total_bounces, r.total_distance / max(1, r.total_bounces)))
print("all OK")
