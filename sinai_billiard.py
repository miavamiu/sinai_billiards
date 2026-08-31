"""
=============================================================================
  SINAI BILLIARD SIMULATION  (beginner version, no extra packages needed)
=============================================================================
  What is a Sinai billiard?
  -------------------------
  A point "ball" flies in a straight line inside a board (rectangle, circle,
  ellipse, or a polar curve). Optionally there is an obstacle
  (prepyatstvie / scatterer) inside; you can also run with
  obstacle = "none" (empty table).
  When the ball hits a wall or the obstacle, it bounces elastically:
  angle of incidence = angle of reflection.

  This system was studied by Yakov Sinai. It is famous for CHAOS:
  a tiny change in the start angle can create a totally different path.

  What YOU can control:
    - board shape: rectangle, circle, ellipse, or polar curve
      polar: r(θ) = r0 + a1 cosθ + b1 sinθ + a2 cos2θ + b2 sin2θ + ...
      (useful for studying bounce behaviour at small iteration counts)
    - side ratio of the rectangle / ellipse (width / height)
    - obstacle shape (or "none" = empty table, no scatterer)
    - obstacle size and placement (when an obstacle is present)
    - ball start position and start angle ONLY (speed is always 1)
    - how many bounces / how long each trial runs

  After each trial you get tables you can copy into Google Sheets.
  Results are also saved as CSV files (open them in Google Sheets).

  How to run (Windows):
      py sinai_billiard.py

  Needs ONLY normal Python (uses tkinter for the picture).
  No pip install required.
=============================================================================
"""

# ---------------------------------------------------------------------------
# IMPORTS - built-in Python tools (nothing to install)
# ---------------------------------------------------------------------------
import math          # sin, cos, pi, sqrt, atan2, ...
import csv           # save tables as CSV for Google Sheets
import copy          # make copies of settings for each trial
import os            # to show the full file path of saved results
from dataclasses import dataclass  # neat boxes for settings / results

# tkinter draws the billiard window (comes with Python on Windows)
import tkinter as tk


# =============================================================================
# CONFIG - CHANGE DEFAULTS HERE, or use the interactive menu when you run
# =============================================================================
# Angles are in DEGREES:  0 = right, 90 = up, 180 = left, 270 = down
# Board center is always at (0, 0)

@dataclass
class Config:
    """All settings in one place. A dataclass is just a named box of values."""

    # ----- BOARD -----
    # Allowed: "rectangle", "circle", "ellipse", or "polar"
    board_shape: str = "rectangle"

    # Rectangle / ellipse only: width = ratio * height
    #   1.0 -> square (or circle),  2.0 -> twice as wide as tall
    # Circle / polar board: this value is ignored
    board_ratio: float = 1.5

    # Size of the board:
    #   rectangle -> half-height  (full height = 2*board_size,
    #                              full width  = 2*board_size*board_ratio)
    #   circle    -> radius
    #   ellipse   -> vertical radius (horizontal radius = board_size*board_ratio)
    #   polar     -> ignored (use polar_r0 / polar_a* / polar_b* below)
    board_size: float = 1.0

    # Polar board: r(θ) = r0 + a1 cosθ + b1 sinθ
    #                    + a2 cos2θ + b2 sin2θ
    #                    + a3 cos3θ + b3 sin3θ
    # Require r(θ) >= 0 for all θ (star-shaped domain around the origin).
    # r(θ) = 0 at one angle is allowed and means a CUSP there.
    # Example limaçon-ish: r0=1, a1=0.3, rest 0
    # Cardioid (proven fully chaotic): r0=1, a1=1, rest 0
    polar_r0: float = 1.0
    polar_a1: float = 0.0
    polar_b1: float = 0.0
    polar_a2: float = 0.0
    polar_b2: float = 0.0
    polar_a3: float = 0.0
    polar_b3: float = 0.0

    # ----- OBSTACLE (prepyatstvie) -----
    # Allowed: "circle", "ellipse", "rectangle", or "none" (no obstacle)
    obstacle_shape: str = "circle"

    # Center of the obstacle (relative to board center)
    obstacle_x: float = 0.0
    obstacle_y: float = 0.0

    # Size:
    #   circle    -> obstacle_rx = radius; obstacle_ry ignored
    #   ellipse   -> obstacle_rx = horizontal radius, obstacle_ry = vertical
    #   rectangle -> obstacle_rx = half-width, obstacle_ry = half-height
    obstacle_rx: float = 0.35
    obstacle_ry: float = 0.25

    # ----- BALL -----
    # Must start INSIDE the board and OUTSIDE the obstacle
    start_x: float = 0.7
    start_y: float = 0.0

    # Starting direction in degrees
    start_angle_deg: float = 35.0

    # Speed is kept at 1.0 so path shape depends only on angle + geometry
    speed: float = 1.0

    # ----- HOW LONG ONE TRIAL RUNS -----
    max_bounces: int = 80          # stop after this many hits
    max_distance: float = 50.0     # or after this much path length

    # Tiny push after a bounce so the ball does not stick to the wall
    epsilon: float = 1e-9

    # ----- OUTPUT -----
    show_plot: bool = True
    save_csv_file: str = "sinai_results.csv"


# Default settings object used by the program
CFG = Config()


# =============================================================================
# GEOMETRY HELPERS
# =============================================================================

def board_half_extents(cfg: Config):
    """
    Return (half_width, half_height) of the rectangular board.
    For an ellipse board these same two numbers are its radii (rx, ry).
    For a circle / polar board we still use this as a drawing bounding box helper.
    """
    half_h = cfg.board_size
    half_w = cfg.board_size * cfg.board_ratio
    return half_w, half_h


def board_ellipse_radii(cfg: Config):
    """Return (rx, ry): horizontal and vertical radii of an ellipse board."""
    return board_half_extents(cfg)


def polar_radius(theta, cfg: Config) -> float:
    """
    r(θ) for a polar board:
      r0 + a1 cosθ + b1 sinθ + a2 cos2θ + b2 sin2θ + a3 cos3θ + b3 sin3θ
    """
    r = cfg.polar_r0
    r += cfg.polar_a1 * math.cos(theta) + cfg.polar_b1 * math.sin(theta)
    r += cfg.polar_a2 * math.cos(2.0 * theta) + cfg.polar_b2 * math.sin(2.0 * theta)
    r += cfg.polar_a3 * math.cos(3.0 * theta) + cfg.polar_b3 * math.sin(3.0 * theta)
    return r


def polar_radius_deriv(theta, cfg: Config) -> float:
    """Derivative dr/dθ of the polar radius (for bounce normals)."""
    dr = -cfg.polar_a1 * math.sin(theta) + cfg.polar_b1 * math.cos(theta)
    dr += (-2.0 * cfg.polar_a2 * math.sin(2.0 * theta)
           + 2.0 * cfg.polar_b2 * math.cos(2.0 * theta))
    dr += (-3.0 * cfg.polar_a3 * math.sin(3.0 * theta)
           + 3.0 * cfg.polar_b3 * math.cos(3.0 * theta))
    return dr


def polar_inward_normal(theta, cfg: Config):
    """
    Unit normal at boundary angle θ, pointing INTO free space (inside the board).

    Boundary: X(θ) = r(θ) (cosθ, sinθ)
    Tangent:  X'(θ) = (r' cosθ - r sinθ, r' sinθ + r cosθ)
    Inward = (-X'_y, X'_x)  (for a circle this is -radial)
    """
    r = polar_radius(theta, cfg)
    dr = polar_radius_deriv(theta, cfg)
    c = math.cos(theta)
    s = math.sin(theta)
    nx = -(dr * s + r * c)
    ny = dr * c - r * s
    length = math.hypot(nx, ny)
    if length < 1e-15:
        return None
    return nx / length, ny / length


def polar_coefficients(cfg: Config):
    """The 7 numbers that fully define the polar curve r(θ)."""
    return (
        cfg.polar_r0,
        cfg.polar_a1, cfg.polar_b1,
        cfg.polar_a2, cfg.polar_b2,
        cfg.polar_a3, cfg.polar_b3,
    )


# r(θ) extrema depend only on the 7 coefficients, but hit_polar_board needs
# max_polar_radius on EVERY collision. Sampling 720 points each time made the
# chaos survey unusably slow, so remember the answer per coefficient set.
_POLAR_EXTREMA_CACHE = {}


def _polar_extrema(cfg: Config, samples: int):
    """Return (min r, max r) over a dense sample, cached per curve."""
    key = (polar_coefficients(cfg), samples)
    hit = _POLAR_EXTREMA_CACHE.get(key)
    if hit is not None:
        return hit
    lo = float("inf")
    hi = 0.0
    for i in range(samples):
        theta = 2.0 * math.pi * i / samples
        r = polar_radius(theta, cfg)
        lo = min(lo, r)
        hi = max(hi, r)
    _POLAR_EXTREMA_CACHE[key] = (lo, hi)
    return lo, hi


def max_polar_radius(cfg: Config, samples: int = 720) -> float:
    """Largest r(θ) over a dense sample (for window scaling / ray search)."""
    return _polar_extrema(cfg, samples)[1]


def min_polar_radius(cfg: Config, samples: int = 720) -> float:
    """Smallest r(θ) over a dense sample (must stay > 0)."""
    return _polar_extrema(cfg, samples)[0]


def board_world_half_size(cfg: Config):
    """Half-width and half-height of a box that contains the whole board."""
    if cfg.board_shape == "rectangle":
        return board_half_extents(cfg)
    if cfg.board_shape == "circle":
        R = cfg.board_size
        return R, R
    if cfg.board_shape == "ellipse":
        return board_ellipse_radii(cfg)
    if cfg.board_shape == "polar":
        R = max_polar_radius(cfg)
        return R, R
    raise ValueError("Unknown board_shape: " + str(cfg.board_shape))


def point_inside_board(x, y, cfg: Config) -> bool:
    """True if (x, y) is strictly inside the board."""
    if cfg.board_shape == "rectangle":
        hw, hh = board_half_extents(cfg)
        return abs(x) < hw and abs(y) < hh
    if cfg.board_shape == "circle":
        return x * x + y * y < cfg.board_size * cfg.board_size
    if cfg.board_shape == "ellipse":
        rx, ry = board_ellipse_radii(cfg)
        if rx <= 0 or ry <= 0:
            return False
        return (x / rx) ** 2 + (y / ry) ** 2 < 1.0
    if cfg.board_shape == "polar":
        rho = math.hypot(x, y)
        if rho < 1e-15:
            # The origin is interior only when the curve never reaches it.
            # On a cusped board (e.g. the cardioid) the cusp sits ON the
            # origin, so the origin is a boundary point, not free space.
            return min_polar_radius(cfg) > 0.0
        theta = math.atan2(y, x)
        return rho < polar_radius(theta, cfg)
    raise ValueError("Unknown board_shape: " + str(cfg.board_shape))


def boundary_distance(cfg: Config, theta: float) -> float:
    """
    Distance from the board centre (0, 0) out to the wall along direction theta.

    Found by bisection on point_inside_board, so it works for every board shape
    (including ones added later) without shape-specific formulas. Returns 0.0
    when there is no free space in that direction at all - which happens on a
    cusped board like the cardioid, exactly along the cusp.
    """
    c = math.cos(theta)
    s = math.sin(theta)
    hw, hh = board_world_half_size(cfg)
    far = math.hypot(hw, hh) * 1.5 + 1.0   # certainly outside the board

    # Halve inward until we land inside. Every board here is star-shaped about
    # the centre, so the inside radii form one interval [0, R).
    lo = None
    probe = far
    for _ in range(80):
        probe *= 0.5
        if point_inside_board(probe * c, probe * s, cfg):
            lo = probe
            break
    if lo is None:
        return 0.0

    hi = far
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if point_inside_board(mid * c, mid * s, cfg):
            lo = mid
        else:
            hi = mid
    return lo


# 360 * (1 - 1/phi). Successive multiples of this angle never repeat a
# direction and never line up with the symmetry axes at 0/45/90/... degrees.
GOLDEN_ANGLE_DEG = 137.50776405003785


def spread_start_points(cfg: Config, n_points: int = 5, fill: float = 0.92):
    """
    Pick n_points start positions spread over the board on a golden-angle
    ("sunflower") spiral: point k sits at angle (k+0.5)*137.5 deg and at
    sqrt((k+0.5)/n) of the way to the wall along that direction.

    Why this pattern rather than named spots like the centre and the corners:

      - The golden angle is irrational against a full turn, so no point ever
        lands on a symmetry axis. Symmetry positions sample special orbit
        families; measured against area-sampled points they understated the
        real spread of the chaoticness score by about 5x.
      - The sqrt radial spacing makes the points uniform BY AREA, so the set
        is representative instead of bunched near the middle.
      - No point sits at the exact centre, which is both a symmetry point and,
        on a cusped board like the cardioid, not even inside the board.
      - Each radius is scaled by the wall distance in its own direction, so
        the spread adapts to lopsided boards.
    """
    n = max(1, int(n_points))
    points = []
    for k in range(n):
        theta = math.radians(GOLDEN_ANGLE_DEG * (k + 0.5))
        reach = boundary_distance(cfg, theta)
        if reach <= 0.0:
            continue
        radius = fill * math.sqrt((k + 0.5) / n) * reach
        x = radius * math.cos(theta)
        y = radius * math.sin(theta)
        if not point_inside_board(x, y, cfg):
            continue
        if point_inside_obstacle(x, y, cfg):
            continue
        points.append((x, y))
    return points


def point_inside_obstacle(x, y, cfg: Config) -> bool:
    """True if (x, y) is inside the solid obstacle."""
    if cfg.obstacle_shape == "none":
        return False

    # Move origin to the obstacle center
    dx = x - cfg.obstacle_x
    dy = y - cfg.obstacle_y

    if cfg.obstacle_shape == "circle":
        r = cfg.obstacle_rx
        return dx * dx + dy * dy <= r * r

    if cfg.obstacle_shape == "ellipse":
        rx, ry = cfg.obstacle_rx, cfg.obstacle_ry
        if rx <= 0 or ry <= 0:
            return False
        # Inside ellipse test: (dx/rx)^2 + (dy/ry)^2 <= 1
        return (dx / rx) ** 2 + (dy / ry) ** 2 <= 1.0

    if cfg.obstacle_shape == "rectangle":
        return abs(dx) <= cfg.obstacle_rx and abs(dy) <= cfg.obstacle_ry

    raise ValueError("Unknown obstacle_shape: " + str(cfg.obstacle_shape))


def validate_start(cfg: Config):
    """Crash early with a clear message if the start point is illegal."""
    if cfg.board_shape == "polar":
        # r(θ) = 0 at a single angle is a CUSP, which is allowed: it is what
        # makes the cardioid (r0=1, a1=1) - a billiard proven fully chaotic -
        # expressible here. Only a NEGATIVE radius is rejected, because that
        # flips points through the origin and no longer describes a simple
        # closed boundary.
        r_min = min_polar_radius(cfg)
        if r_min < -1e-12:
            raise ValueError(
                "Polar board has r(theta) < 0 somewhere (min = {:.4f}). "
                "A negative radius does not describe a closed boundary. "
                "Increase polar_r0 or reduce the a/b coefficients "
                "(r(theta) = 0 at one angle is fine - that is a cusp)."
                .format(r_min)
            )
    if cfg.board_shape == "ellipse":
        rx, ry = board_ellipse_radii(cfg)
        if rx <= 0 or ry <= 0:
            raise ValueError(
                "Ellipse board needs positive radii (got rx = {:.4f}, ry = {:.4f}). "
                "Make board_size and board_ratio positive.".format(rx, ry)
            )
    if not point_inside_board(cfg.start_x, cfg.start_y, cfg):
        raise ValueError(
            "Start (" + str(cfg.start_x) + ", " + str(cfg.start_y) +
            ") is outside the board. Move start_x / start_y inward."
        )
    if point_inside_obstacle(cfg.start_x, cfg.start_y, cfg):
        raise ValueError(
            "Start (" + str(cfg.start_x) + ", " + str(cfg.start_y) +
            ") is inside the obstacle. Move the ball or change the obstacle."
        )


# =============================================================================
# MATH: ray intersections
# =============================================================================
# The ball moves on a ray:
#     position(t) = (x, y) + t * (vx, vy)     with t >= 0
# Because speed = 1, the number t is both "time" and "distance traveled".
# We always want the SMALLEST t > 0 where we hit something.

def solve_quadratic(a, b, c):
    """
    Solve a*t^2 + b*t + c = 0.
    Return a list of real roots (0, 1, or 2 numbers).
    """
    if abs(a) < 1e-15:
        # Becomes linear: b*t + c = 0
        if abs(b) < 1e-15:
            return []
        return [-c / b]

    disc = b * b - 4.0 * a * c   # discriminant
    if disc < 0:
        return []                # no real hit
    if disc == 0:
        return [-b / (2.0 * a)]
    s = math.sqrt(disc)
    return [(-b - s) / (2.0 * a), (-b + s) / (2.0 * a)]


def earliest_positive(times, eps=1e-10):
    """Return the smallest time > eps, or None."""
    good = [t for t in times if t > eps]
    if not good:
        return None
    return min(good)


# ----- hits with the OUTER board -----

def hit_rectangle_board(x, y, vx, vy, cfg: Config):
    """
    Next hit with rectangular outer walls.
    Returns (t, nx, ny) where (nx, ny) is the INWARD unit normal
    (points into free space - needed for the bounce formula).

    Corner case:
      If the ball hits an exact corner, TWO walls are hit at the same time.
      We combine both normals so the ball bounces back INTO the board
      (instead of "escaping" through the other wall and stopping).
    """
    hw, hh = board_half_extents(cfg)
    candidates = []

    # Right wall x = +hw ; inward normal = (-1, 0)
    if abs(vx) > 1e-15:
        t = (hw - x) / vx
        if t > 1e-10:
            yy = y + t * vy
            if -hh - 1e-12 <= yy <= hh + 1e-12:
                candidates.append((t, -1.0, 0.0))

    # Left wall x = -hw ; inward normal = (+1, 0)
    if abs(vx) > 1e-15:
        t = (-hw - x) / vx
        if t > 1e-10:
            yy = y + t * vy
            if -hh - 1e-12 <= yy <= hh + 1e-12:
                candidates.append((t, 1.0, 0.0))

    # Top wall y = +hh ; inward normal = (0, -1)
    if abs(vy) > 1e-15:
        t = (hh - y) / vy
        if t > 1e-10:
            xx = x + t * vx
            if -hw - 1e-12 <= xx <= hw + 1e-12:
                candidates.append((t, 0.0, -1.0))

    # Bottom wall y = -hh ; inward normal = (0, +1)
    if abs(vy) > 1e-15:
        t = (-hh - y) / vy
        if t > 1e-10:
            xx = x + t * vx
            if -hw - 1e-12 <= xx <= hw + 1e-12:
                candidates.append((t, 0.0, 1.0))

    if not candidates:
        return None

    # Earliest hit time
    t_min = min(item[0] for item in candidates)
    # All walls hit at (almost) that same time - usually 1 wall, or 2 at a corner
    near = [item for item in candidates if abs(item[0] - t_min) < 1e-9]
    nx = sum(item[1] for item in near)
    ny = sum(item[2] for item in near)
    length = math.hypot(nx, ny)
    if length < 1e-15:
        return None
    return (t_min, nx / length, ny / length)


def hit_circle_board(x, y, vx, vy, cfg: Config):
    """Next hit with circular outer wall of radius R = board_size."""
    R = cfg.board_size
    # |P + t V|^2 = R^2
    a = vx * vx + vy * vy
    b = 2.0 * (x * vx + y * vy)
    c = x * x + y * y - R * R
    t = earliest_positive(solve_quadratic(a, b, c))
    if t is None:
        return None
    hx = x + t * vx
    hy = y + t * vy
    length = math.hypot(hx, hy)
    if length < 1e-15:
        return None
    # Outward normal is (hx, hy); inward is opposite
    return (t, -hx / length, -hy / length)


def hit_ellipse_board(x, y, vx, vy, cfg: Config):
    """
    Next hit with an axis-aligned elliptical outer wall
    (radii rx = board_size*board_ratio, ry = board_size).

    Same trick as the ellipse obstacle: scale space so the ellipse becomes the
    unit circle, solve the quadratic there, then map the normal back.
    """
    rx, ry = board_ellipse_radii(cfg)
    if rx <= 0 or ry <= 0:
        return None

    px = x / rx
    py = y / ry
    svx = vx / rx
    svy = vy / ry

    a = svx * svx + svy * svy
    b = 2.0 * (px * svx + py * svy)
    c = px * px + py * py - 1.0
    t = earliest_positive(solve_quadratic(a, b, c))
    if t is None:
        return None

    hx = px + t * svx
    hy = py + t * svy
    # Gradient mapped back to world coordinates points OUT of the board;
    # the bounce formula needs the INWARD normal, so flip the sign.
    nx = -hx / rx
    ny = -hy / ry
    length = math.hypot(nx, ny)
    if length < 1e-15:
        return None
    return (t, nx / length, ny / length)


def _polar_signed_gap(x, y, vx, vy, t, cfg: Config) -> float:
    """
    f(t) = |P(t)| - r(arg P(t)).
    Negative => inside the polar board; zero => on the boundary.
    """
    px = x + t * vx
    py = y + t * vy
    rho = math.hypot(px, py)
    if rho < 1e-15:
        # At the origin: always inside for a positive polar curve
        return -polar_radius(0.0, cfg)
    theta = math.atan2(py, px)
    return rho - polar_radius(theta, cfg)


def hit_polar_board(x, y, vx, vy, cfg: Config):
    """
    Next hit with a polar outer wall r(θ).

    No closed-form quadratic in general, so we:
      1) scan along the ray for the first inside->outside crossing of f(t)=0
      2) refine the root by bisection
      3) build the inward normal from r(θ) and r'(θ)
    """
    r_max = max_polar_radius(cfg)
    if r_max <= 0:
        return None

    # Search far enough to always reach the boundary from inside
    t_max = max(4.0 * r_max, 4.0)
    n_steps = 800
    dt = t_max / n_steps

    f_prev = _polar_signed_gap(x, y, vx, vy, 0.0, cfg)
    t_prev = 0.0
    t_hit = None

    for i in range(1, n_steps + 1):
        t = i * dt
        f = _polar_signed_gap(x, y, vx, vy, t, cfg)
        # First exit: f goes from negative (inside) to non-negative (outside)
        if f_prev < 0.0 and f >= 0.0 and t > 1e-10:
            # Bisection refine
            lo, hi = t_prev, t
            flo = f_prev
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                fmid = _polar_signed_gap(x, y, vx, vy, mid, cfg)
                if flo < 0.0 and fmid >= 0.0:
                    hi = mid
                else:
                    lo = mid
                    flo = fmid
            t_hit = hi
            break
        f_prev = f
        t_prev = t

    if t_hit is None:
        return None

    hx = x + t_hit * vx
    hy = y + t_hit * vy
    theta = math.atan2(hy, hx)
    normal = polar_inward_normal(theta, cfg)
    if normal is None:
        return None
    nx, ny = normal
    return (t_hit, nx, ny)


def next_board_hit(x, y, vx, vy, cfg: Config):
    if cfg.board_shape == "rectangle":
        return hit_rectangle_board(x, y, vx, vy, cfg)
    if cfg.board_shape == "circle":
        return hit_circle_board(x, y, vx, vy, cfg)
    if cfg.board_shape == "ellipse":
        return hit_ellipse_board(x, y, vx, vy, cfg)
    if cfg.board_shape == "polar":
        return hit_polar_board(x, y, vx, vy, cfg)
    raise ValueError("Unknown board_shape: " + str(cfg.board_shape))


# ----- hits with the OBSTACLE -----

def hit_circle_obstacle(x, y, vx, vy, cfg: Config):
    """Next hit with a circular obstacle."""
    ox, oy = cfg.obstacle_x, cfg.obstacle_y
    r = cfg.obstacle_rx
    px, py = x - ox, y - oy

    a = vx * vx + vy * vy
    b = 2.0 * (px * vx + py * vy)
    c = px * px + py * py - r * r
    t = earliest_positive(solve_quadratic(a, b, c))
    if t is None:
        return None

    hx = px + t * vx
    hy = py + t * vy
    length = math.hypot(hx, hy)
    if length < 1e-15:
        return None
    # Normal points OUT of the solid disc (into free space)
    return (t, hx / length, hy / length)


def hit_ellipse_obstacle(x, y, vx, vy, cfg: Config):
    """
    Next hit with an axis-aligned ellipse.
    Trick: scale space so the ellipse becomes the unit circle, solve there,
    then map the normal back to real space.
    """
    ox, oy = cfg.obstacle_x, cfg.obstacle_y
    rx, ry = cfg.obstacle_rx, cfg.obstacle_ry
    if rx <= 0 or ry <= 0:
        return None

    px = (x - ox) / rx
    py = (y - oy) / ry
    svx = vx / rx
    svy = vy / ry

    a = svx * svx + svy * svy
    b = 2.0 * (px * svx + py * svy)
    c = px * px + py * py - 1.0
    t = earliest_positive(solve_quadratic(a, b, c))
    if t is None:
        return None

    hx = px + t * svx
    hy = py + t * svy
    # Gradient mapped back to world coordinates
    nx = hx / rx
    ny = hy / ry
    length = math.hypot(nx, ny)
    if length < 1e-15:
        return None
    return (t, nx / length, ny / length)


def hit_rectangle_obstacle(x, y, vx, vy, cfg: Config):
    """Next hit with a solid axis-aligned rectangular obstacle."""
    ox, oy = cfg.obstacle_x, cfg.obstacle_y
    rx, ry = cfg.obstacle_rx, cfg.obstacle_ry
    left, right = ox - rx, ox + rx
    bottom, top = oy - ry, oy + ry
    candidates = []

    # Right face (outside is to the right; need vx < 0 to approach it)
    if abs(vx) > 1e-15:
        t = (right - x) / vx
        if t > 1e-10:
            yy = y + t * vy
            if bottom <= yy <= top and vx < 0:
                candidates.append((t, 1.0, 0.0))

    # Left face
    if abs(vx) > 1e-15:
        t = (left - x) / vx
        if t > 1e-10:
            yy = y + t * vy
            if bottom <= yy <= top and vx > 0:
                candidates.append((t, -1.0, 0.0))

    # Top face
    if abs(vy) > 1e-15:
        t = (top - y) / vy
        if t > 1e-10:
            xx = x + t * vx
            if left <= xx <= right and vy < 0:
                candidates.append((t, 0.0, 1.0))

    # Bottom face
    if abs(vy) > 1e-15:
        t = (bottom - y) / vy
        if t > 1e-10:
            xx = x + t * vx
            if left <= xx <= right and vy > 0:
                candidates.append((t, 0.0, -1.0))

    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])


def next_obstacle_hit(x, y, vx, vy, cfg: Config):
    if cfg.obstacle_shape == "none":
        return None
    if cfg.obstacle_shape == "circle":
        return hit_circle_obstacle(x, y, vx, vy, cfg)
    if cfg.obstacle_shape == "ellipse":
        return hit_ellipse_obstacle(x, y, vx, vy, cfg)
    if cfg.obstacle_shape == "rectangle":
        return hit_rectangle_obstacle(x, y, vx, vy, cfg)
    raise ValueError("Unknown obstacle_shape: " + str(cfg.obstacle_shape))


# =============================================================================
# BOUNCE (reflection law)
# =============================================================================

def reflect(vx, vy, nx, ny):
    """
    Elastic bounce of velocity V on a surface with unit normal N
    (N points into free space).

    Formula:
        V_new = V - 2 * (V dot N) * N

    Idea: keep the part of V that is parallel to the wall,
    and flip the part that goes into the wall.
    """
    # V dot N  (how much of V points along the normal)
    dot = vx * nx + vy * ny
    rx = vx - 2.0 * dot * nx
    ry = vy - 2.0 * dot * ny
    # Keep speed exactly 1 (fix tiny floating-point drift)
    length = math.hypot(rx, ry)
    if length > 0:
        rx /= length
        ry /= length
    return rx, ry


def angle_of_velocity(vx, vy):
    """Turn velocity into an angle in degrees, range [0, 360)."""
    deg = math.degrees(math.atan2(vy, vx))
    if deg < 0:
        deg += 360.0
    return deg


# =============================================================================
# DATA RECORDED DURING A TRIAL
# =============================================================================

@dataclass
class BounceEvent:
    """One bounce = one row in the detailed table."""
    bounce_index: int
    hit_what: str            # "board" or "obstacle"
    x: float
    y: float
    angle_in_deg: float      # direction before bounce
    angle_out_deg: float     # direction after bounce
    distance_segment: float  # flight length since previous bounce
    distance_total: float    # total path length so far


@dataclass
class TrialResult:
    """Everything we learned from one full run."""
    trial_id: int
    cfg_snapshot: dict
    path_x: list
    path_y: list
    bounces: list
    total_distance: float
    total_bounces: int
    board_hits: int
    obstacle_hits: int


# =============================================================================
# RUN ONE TRIAL
# =============================================================================

def run_trial(cfg: Config, trial_id: int = 1) -> TrialResult:
    """
    Simulate the billiard until max_bounces or max_distance.
    Returns a TrialResult with the path and bounce table.
    """
    validate_start(cfg)

    # Current position
    x = float(cfg.start_x)
    y = float(cfg.start_y)

    # Current velocity from the start angle (unit vector * speed)
    ang = math.radians(cfg.start_angle_deg)
    vx = math.cos(ang) * cfg.speed
    vy = math.sin(ang) * cfg.speed
    speed = math.hypot(vx, vy)
    vx /= speed
    vy /= speed

    # Lists that store the drawn path
    path_x = [x]
    path_y = [y]

    bounces = []
    total_distance = 0.0
    board_hits = 0
    obstacle_hits = 0

    for bounce_i in range(1, cfg.max_bounces + 1):
        # Ask: where do we hit the board? where do we hit the obstacle?
        board = next_board_hit(x, y, vx, vy, cfg)
        obst = next_obstacle_hit(x, y, vx, vy, cfg)

        # Keep the closer hit
        choice = None  # ("board"|"obstacle", t, nx, ny)
        if board is not None:
            choice = ("board",) + board
        if obst is not None:
            if choice is None or obst[0] < choice[1]:
                choice = ("obstacle",) + obst

        if choice is None:
            break  # safety; should almost never happen

        hit_what, t, nx, ny = choice

        # If the next hit would go past max_distance, stop mid-flight
        if total_distance + t > cfg.max_distance:
            remain = cfg.max_distance - total_distance
            x = x + remain * vx
            y = y + remain * vy
            path_x.append(x)
            path_y.append(y)
            total_distance = cfg.max_distance
            break

        angle_in = angle_of_velocity(vx, vy)

        # Fly to the hit point
        x = x + t * vx
        y = y + t * vy
        total_distance += t
        path_x.append(x)
        path_y.append(y)

        # Bounce
        vx, vy = reflect(vx, vy, nx, ny)
        angle_out = angle_of_velocity(vx, vy)

        # Tiny nudge INTO free space (along the normal), so we do not
        # stick to the wall or slip outside through a corner
        nudge = max(cfg.epsilon, 1e-8)
        x = x + nudge * nx
        y = y + nudge * ny

        if hit_what == "board":
            board_hits += 1
        else:
            obstacle_hits += 1

        bounces.append(
            BounceEvent(
                bounce_index=bounce_i,
                hit_what=hit_what,
                x=x,
                y=y,
                angle_in_deg=angle_in,
                angle_out_deg=angle_out,
                distance_segment=t,
                distance_total=total_distance,
            )
        )

    hw, hh = board_world_half_size(cfg)
    snapshot = {
        "trial_id": trial_id,
        "board_shape": cfg.board_shape,
        "board_ratio": cfg.board_ratio,
        "board_size": cfg.board_size,
        "board_half_width": hw,
        "board_half_height": hh,
        "polar_r0": cfg.polar_r0,
        "polar_a1": cfg.polar_a1,
        "polar_b1": cfg.polar_b1,
        "polar_a2": cfg.polar_a2,
        "polar_b2": cfg.polar_b2,
        "polar_a3": cfg.polar_a3,
        "polar_b3": cfg.polar_b3,
        "obstacle_shape": cfg.obstacle_shape,
        "obstacle_x": cfg.obstacle_x,
        "obstacle_y": cfg.obstacle_y,
        "obstacle_rx": cfg.obstacle_rx,
        "obstacle_ry": cfg.obstacle_ry,
        "start_x": cfg.start_x,
        "start_y": cfg.start_y,
        "start_angle_deg": cfg.start_angle_deg,
        "max_bounces": cfg.max_bounces,
        "max_distance": cfg.max_distance,
    }

    return TrialResult(
        trial_id=trial_id,
        cfg_snapshot=snapshot,
        path_x=path_x,
        path_y=path_y,
        bounces=bounces,
        total_distance=total_distance,
        total_bounces=len(bounces),
        board_hits=board_hits,
        obstacle_hits=obstacle_hits,
    )


# =============================================================================
# ANALYSIS TABLES (copy-paste into Google Sheets)
# =============================================================================
# Tip: tables use TAB characters between columns.
# In Google Sheets: paste, then Data -> Split text to columns -> Separator = Tab.
# Or upload the CSV files (File -> Import).

def _mean_segment(result: TrialResult) -> float:
    if result.total_bounces == 0:
        return 0.0
    return result.total_distance / result.total_bounces


def _obstacle_fraction(result: TrialResult) -> float:
    if result.total_bounces == 0:
        return 0.0
    return result.obstacle_hits / result.total_bounces


def print_summary_table(result: TrialResult):
    """One-line summary of a trial (TAB-separated)."""
    s = result.cfg_snapshot
    headers = [
        "trial_id", "board_shape", "board_ratio",
        "polar_r0", "polar_a1", "polar_b1", "polar_a2", "polar_b2", "polar_a3", "polar_b3",
        "obstacle_shape",
        "obstacle_x", "obstacle_y", "obstacle_rx", "obstacle_ry",
        "start_x", "start_y", "start_angle_deg",
        "total_bounces", "board_hits", "obstacle_hits",
        "total_distance", "mean_segment_length", "obstacle_hit_fraction",
    ]
    values = [
        s["trial_id"],
        s["board_shape"],
        s["board_ratio"],
        s["polar_r0"],
        s["polar_a1"],
        s["polar_b1"],
        s["polar_a2"],
        s["polar_b2"],
        s["polar_a3"],
        s["polar_b3"],
        s["obstacle_shape"],
        s["obstacle_x"],
        s["obstacle_y"],
        s["obstacle_rx"],
        s["obstacle_ry"],
        s["start_x"],
        s["start_y"],
        s["start_angle_deg"],
        result.total_bounces,
        result.board_hits,
        result.obstacle_hits,
        "{:.6f}".format(result.total_distance),
        "{:.6f}".format(_mean_segment(result)),
        "{:.6f}".format(_obstacle_fraction(result)),
    ]
    print("\n=== SUMMARY (copy into Google Sheets) ===")
    print("\t".join(headers))
    print("\t".join(str(v) for v in values))
    print("=== END SUMMARY ===\n")


def print_bounce_table(result: TrialResult):
    """Every bounce as its own row (TAB-separated)."""
    headers = [
        "trial_id", "bounce_index", "hit_what", "x", "y",
        "angle_in_deg", "angle_out_deg", "distance_segment", "distance_total",
    ]
    print("=== BOUNCE TABLE (copy into Google Sheets) ===")
    print("\t".join(headers))
    for b in result.bounces:
        row = [
            result.trial_id,
            b.bounce_index,
            b.hit_what,
            "{:.6f}".format(b.x),
            "{:.6f}".format(b.y),
            "{:.6f}".format(b.angle_in_deg),
            "{:.6f}".format(b.angle_out_deg),
            "{:.6f}".format(b.distance_segment),
            "{:.6f}".format(b.distance_total),
        ]
        print("\t".join(str(v) for v in row))
    print("=== END BOUNCE TABLE ===\n")


def _round(value, digits=6):
    """Round only real numbers; leave text (like 'circle') untouched."""
    if isinstance(value, float):
        return round(value, digits)
    return value


def save_results_to_csv(results, summary_path: str, bounce_path: str = None):
    """
    Write ALL current results to CSV files, OVERWRITING each time.

    Why overwrite instead of append?
    Appending kept adding the same trials again on every save (and again
    each time you restarted the program), so the file filled up with
    duplicate rows. Overwriting means the file always matches exactly the
    trials you have run in THIS session - no duplicates, no leftovers.

    CSV = Comma Separated Values - Google Sheets opens these easily
    (File -> Import -> Upload, separator = comma).
    """
    if bounce_path is None:
        if summary_path.lower().endswith(".csv"):
            bounce_path = summary_path[:-4] + "_bounces.csv"
        else:
            bounce_path = summary_path + "_bounces.csv"

    # --- summary file (one row per trial) ---
    summary_headers = [
        "trial_id", "board_shape", "board_ratio",
        "polar_r0", "polar_a1", "polar_b1", "polar_a2", "polar_b2", "polar_a3", "polar_b3",
        "obstacle_shape",
        "obstacle_x", "obstacle_y", "obstacle_rx", "obstacle_ry",
        "start_x", "start_y", "start_angle_deg",
        "total_bounces", "board_hits", "obstacle_hits",
        "total_distance", "mean_segment_length", "obstacle_hit_fraction",
    ]
    # "w" = write from scratch (overwrite). This is the key fix.
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(summary_headers)
        for result in results:
            s = result.cfg_snapshot
            writer.writerow([_round(v) for v in [
                s["trial_id"], s["board_shape"], s["board_ratio"],
                s["polar_r0"], s["polar_a1"], s["polar_b1"],
                s["polar_a2"], s["polar_b2"], s["polar_a3"], s["polar_b3"],
                s["obstacle_shape"],
                s["obstacle_x"], s["obstacle_y"], s["obstacle_rx"], s["obstacle_ry"],
                s["start_x"], s["start_y"], s["start_angle_deg"],
                result.total_bounces, result.board_hits, result.obstacle_hits,
                result.total_distance, _mean_segment(result), _obstacle_fraction(result),
            ]])

    # --- bounce detail file (one row per bounce) ---
    bounce_headers = [
        "trial_id", "bounce_index", "hit_what", "x", "y",
        "angle_in_deg", "angle_out_deg", "distance_segment", "distance_total",
    ]
    with open(bounce_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(bounce_headers)
        for result in results:
            for b in result.bounces:
                writer.writerow([_round(v) for v in [
                    result.trial_id, b.bounce_index, b.hit_what,
                    b.x, b.y, b.angle_in_deg, b.angle_out_deg,
                    b.distance_segment, b.distance_total,
                ]])

    # Show the FULL path so you know exactly where the files are
    print("Saved {} trial(s).".format(len(results)))
    print("  summary -> " + os.path.abspath(summary_path))
    print("  bounces -> " + os.path.abspath(bounce_path))


# =============================================================================
# DRAWING with tkinter (no matplotlib needed)
# =============================================================================

def world_to_screen(x, y, scale, cx, cy):
    """
    Convert math coordinates (y up) to canvas pixels (y down).
    (cx, cy) is the pixel position of the math origin (0, 0).
    """
    return cx + x * scale, cy - y * scale


def _draw_board_and_obstacle(canvas, cfg: Config, scale, cx, cy):
    """Draw the outer board and the obstacle (the static background)."""
    # --- board ---
    if cfg.board_shape == "rectangle":
        hw, hh = board_half_extents(cfg)
        x0, y0 = world_to_screen(-hw, hh, scale, cx, cy)
        x1, y1 = world_to_screen(hw, -hh, scale, cx, cy)
        canvas.create_rectangle(x0, y0, x1, y1, outline="black", width=2)
    elif cfg.board_shape == "circle":
        R = cfg.board_size
        x0, y0 = world_to_screen(-R, R, scale, cx, cy)
        x1, y1 = world_to_screen(R, -R, scale, cx, cy)
        canvas.create_oval(x0, y0, x1, y1, outline="black", width=2)
    elif cfg.board_shape == "ellipse":
        rx, ry = board_ellipse_radii(cfg)
        x0, y0 = world_to_screen(-rx, ry, scale, cx, cy)
        x1, y1 = world_to_screen(rx, -ry, scale, cx, cy)
        canvas.create_oval(x0, y0, x1, y1, outline="black", width=2)
    elif cfg.board_shape == "polar":
        # Sample the polar curve and draw as a closed polyline
        n = 360
        pts = []
        for i in range(n + 1):
            theta = 2.0 * math.pi * i / n
            r = polar_radius(theta, cfg)
            wx = r * math.cos(theta)
            wy = r * math.sin(theta)
            sx, sy = world_to_screen(wx, wy, scale, cx, cy)
            pts.extend([sx, sy])
        if len(pts) >= 4:
            canvas.create_line(*pts, fill="black", width=2)

    # --- obstacle ---
    if cfg.obstacle_shape == "none":
        return

    ox, oy = cfg.obstacle_x, cfg.obstacle_y
    if cfg.obstacle_shape == "circle":
        r = cfg.obstacle_rx
        x0, y0 = world_to_screen(ox - r, oy + r, scale, cx, cy)
        x1, y1 = world_to_screen(ox + r, oy - r, scale, cx, cy)
        canvas.create_oval(x0, y0, x1, y1, fill="#c0c0c0", outline="black", width=2)
    elif cfg.obstacle_shape == "ellipse":
        rx, ry = cfg.obstacle_rx, cfg.obstacle_ry
        x0, y0 = world_to_screen(ox - rx, oy + ry, scale, cx, cy)
        x1, y1 = world_to_screen(ox + rx, oy - ry, scale, cx, cy)
        canvas.create_oval(x0, y0, x1, y1, fill="#c0c0c0", outline="black", width=2)
    elif cfg.obstacle_shape == "rectangle":
        rx, ry = cfg.obstacle_rx, cfg.obstacle_ry
        x0, y0 = world_to_screen(ox - rx, oy + ry, scale, cx, cy)
        x1, y1 = world_to_screen(ox + rx, oy - ry, scale, cx, cy)
        canvas.create_rectangle(x0, y0, x1, y1, fill="#c0c0c0", outline="black", width=2)


def plot_trial(result: TrialResult, cfg: Config):
    """
    Open a window and ANIMATE the ball moving along its path.

    Controls in the window:
      - Play / Pause button   : start or stop the motion
      - Speed slider           : how fast the ball moves
      - Reset button           : jump back to the start
      - Show full path button  : draw the whole path instantly
      - Close window button    : close and continue the program
    """
    if not cfg.show_plot:
        return

    # Window size in pixels
    W, H = 720, 720
    margin = 40

    # How big is the world we need to show?
    hw, hh = board_world_half_size(cfg)
    world_w = 2 * hw
    world_h = 2 * hh
    # Avoid division by zero if someone sets tiny polar coeffs wrongly
    if world_w < 1e-9:
        world_w = 2.0
    if world_h < 1e-9:
        world_h = 2.0

    # Scale so the board fits inside the window with a margin
    scale = min((W - 2 * margin) / world_w, (H - 2 * margin) / world_h)
    cx, cy = W / 2, H / 2

    root = tk.Tk()
    root.title(
        "Sinai billiard - trial {} | bounces={} board={} obstacle={} dist={:.2f}".format(
            result.trial_id,
            result.total_bounces,
            result.board_hits,
            result.obstacle_hits,
            result.total_distance,
        )
    )
    canvas = tk.Canvas(root, width=W, height=H, bg="white")
    canvas.pack()

    # Draw the static background (board + obstacle)
    _draw_board_and_obstacle(canvas, cfg, scale, cx, cy)

    # Turn the path (in world coordinates) into screen pixel points.
    # spts = [(sx0, sy0), (sx1, sy1), ...]
    spts = [world_to_screen(px, py, scale, cx, cy)
            for px, py in zip(result.path_x, result.path_y)]

    # Length (in pixels) of each straight segment, and the total length.
    seg_len = []
    for i in range(len(spts) - 1):
        (ax, ay), (bx, by) = spts[i], spts[i + 1]
        seg_len.append(math.hypot(bx - ax, by - ay))
    total_len = sum(seg_len)

    # Start (green dot) and end (red square) markers
    sx, sy = spts[0]
    canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill="green", outline="")
    ex, ey = spts[-1]
    canvas.create_rectangle(ex - 5, ey - 5, ex + 5, ey + 5, fill="red", outline="")

    # Legend
    if cfg.obstacle_shape == "none":
        legend = "green = start   red = end   (no obstacle)"
    else:
        legend = "green = start   red = end   gray = obstacle"
    canvas.create_text(
        10, 12, anchor="nw", fill="black",
        text=legend,
    )

    # The moving ball (a small blue dot). We create it once and move it.
    ball = canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5,
                              fill="#1f77b4", outline="")

    # The trail (blue line) that grows as the ball moves.
    trail = canvas.create_line(sx, sy, sx, sy, fill="#1f77b4", width=1)

    # --- animation state (stored in a dict so inner functions can change it) ---
    state = {
        "dist": 0.0,     # how far (in pixels) along the path the ball is
        "playing": True,  # is the animation running?
        "job": None,      # the scheduled "next frame" id (so we can cancel it)
    }

    def position_at(dist):
        """Return the (x, y) pixel point that is `dist` pixels along the path."""
        if dist <= 0:
            return spts[0]
        if dist >= total_len:
            return spts[-1]
        # Walk segment by segment until we find where `dist` lands
        remaining = dist
        for i, length in enumerate(seg_len):
            if remaining <= length:
                (ax, ay), (bx, by) = spts[i], spts[i + 1]
                if length == 0:
                    return (ax, ay)
                frac = remaining / length      # 0..1 inside this segment
                return (ax + (bx - ax) * frac, ay + (by - ay) * frac)
            remaining -= length
        return spts[-1]

    def trail_points(dist):
        """All points from the start up to the current position (for the trail)."""
        pts = [spts[0]]
        remaining = dist
        for i, length in enumerate(seg_len):
            if remaining >= length:
                pts.append(spts[i + 1])
                remaining -= length
            else:
                # Partway through this segment: add the interpolated point and stop
                (ax, ay), (bx, by) = spts[i], spts[i + 1]
                if length > 0:
                    frac = remaining / length
                    pts.append((ax + (bx - ax) * frac, ay + (by - ay) * frac))
                break
        return pts

    def redraw():
        """Update the trail line and the ball position on screen."""
        pts = trail_points(state["dist"])
        flat = []
        for (px, py) in pts:
            flat.extend([px, py])
        if len(flat) >= 4:
            canvas.coords(trail, *flat)
        bx, by = position_at(state["dist"])
        canvas.coords(ball, bx - 5, by - 5, bx + 5, by + 5)

    def tick():
        """One animation frame: advance the ball, then schedule the next frame."""
        if not state["playing"]:
            return
        # speed_slider gives pixels-per-frame
        state["dist"] += float(speed_slider.get())
        if state["dist"] >= total_len:
            state["dist"] = total_len
            redraw()
            state["playing"] = False
            play_btn.config(text="Play")
            return
        redraw()
        # Schedule the next frame in ~20 ms (about 50 frames per second)
        state["job"] = root.after(20, tick)

    def toggle_play():
        """Play/Pause button handler."""
        if state["playing"]:
            state["playing"] = False
            play_btn.config(text="Play")
        else:
            # If we are at the end, start over from the beginning
            if state["dist"] >= total_len:
                state["dist"] = 0.0
            state["playing"] = True
            play_btn.config(text="Pause")
            tick()

    def reset():
        """Jump back to the very start."""
        state["dist"] = 0.0
        redraw()

    def show_full():
        """Draw the whole path instantly (no waiting)."""
        state["playing"] = False
        play_btn.config(text="Play")
        state["dist"] = total_len
        redraw()

    def close_window():
        # Cancel any pending frame so nothing runs after the window closes
        if state["job"] is not None:
            try:
                root.after_cancel(state["job"])
            except Exception:
                pass
        root.destroy()

    # --- control panel (row of buttons + a speed slider) ---
    controls = tk.Frame(root)
    controls.pack(pady=6)

    play_btn = tk.Button(controls, text="Pause", width=8, command=toggle_play)
    play_btn.grid(row=0, column=0, padx=4)

    tk.Button(controls, text="Reset", width=8, command=reset).grid(row=0, column=1, padx=4)
    tk.Button(controls, text="Show full path", command=show_full).grid(row=0, column=2, padx=4)
    tk.Button(controls, text="Close window", command=close_window).grid(row=0, column=4, padx=4)

    tk.Label(controls, text="Speed").grid(row=0, column=3, padx=(16, 2))
    speed_slider = tk.Scale(controls, from_=1, to=40, orient=tk.HORIZONTAL, length=160)
    speed_slider.set(6)   # starting speed (pixels per frame)
    speed_slider.grid(row=1, column=0, columnspan=5, sticky="we", padx=4)

    # If the user clicks the window's X, close cleanly too
    root.protocol("WM_DELETE_WINDOW", close_window)

    # Draw the first frame, then start animating
    redraw()
    tick()

    # Block here until the window is closed
    root.mainloop()


# Distinct colours for overlaid paths (no repeats until 8 trajectories).
MULTI_START_COLORS = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
]


def run_multi_start_trial(cfg: Config, points=None, n_points: int = 5,
                          start_trial_id: int = 1, verbose: bool = True):
    """
    Run one trial from each of several start positions, keeping the start ANGLE
    fixed so position is the only thing that changes.

    `points` overrides the automatic spread (see spread_start_points).
    Returns the list of TrialResult, one per usable start position.
    """
    if points is None:
        points = spread_start_points(cfg, n_points)
    if not points:
        raise ValueError(
            "Could not place any start position inside this board. "
            "Check the board size and the obstacle."
        )

    results = []
    trial_id = start_trial_id
    for (sx, sy) in points:
        probe = copy.deepcopy(cfg)
        probe.start_x = sx
        probe.start_y = sy
        try:
            res = run_trial(probe, trial_id=trial_id)
        except ValueError as err:
            if verbose:
                print("  skipped start ({:+.3f}, {:+.3f}): {}".format(sx, sy, err))
            continue
        results.append(res)
        if verbose:
            print("  start ({:+.3f}, {:+.3f}) -> {} bounces, distance {:.2f}".format(
                sx, sy, res.total_bounces, res.total_distance))
        trial_id += 1
    if not results:
        raise ValueError("Every start position failed to run.")
    return results


def plot_multi_start(results, cfg: Config):
    """
    Draw several trajectories on one board so different regions can be compared
    side by side. Static (no animation) - the point is the comparison.
    """
    if not cfg.show_plot or not results:
        return

    W, H = 760, 760
    margin = 40
    legend_h = 18 * (len(results) + 1) + 12

    hw, hh = board_world_half_size(cfg)
    world_w = 2 * hw if hw > 1e-9 else 2.0
    world_h = 2 * hh if hh > 1e-9 else 2.0

    board_h = H - legend_h
    scale = min((W - 2 * margin) / world_w, (board_h - 2 * margin) / world_h)
    cx, cy = W / 2, legend_h + board_h / 2

    root = tk.Tk()
    root.title(
        "Sinai billiard - {} start positions | board={} obstacle={} angle={:.1f} deg"
        .format(len(results), cfg.board_shape, cfg.obstacle_shape,
                cfg.start_angle_deg)
    )
    canvas = tk.Canvas(root, width=W, height=H, bg="white")
    canvas.pack()

    _draw_board_and_obstacle(canvas, cfg, scale, cx, cy)

    canvas.create_text(
        10, 10, anchor="nw", fill="black",
        text="Same start angle ({:.1f} deg), different start positions. "
             "Dots mark the starts.".format(cfg.start_angle_deg),
    )

    for i, res in enumerate(results):
        colour = MULTI_START_COLORS[i % len(MULTI_START_COLORS)]
        pts = []
        for px, py in zip(res.path_x, res.path_y):
            sx, sy = world_to_screen(px, py, scale, cx, cy)
            pts.extend([sx, sy])
        if len(pts) >= 4:
            canvas.create_line(*pts, fill=colour, width=1)

        sx, sy = world_to_screen(res.path_x[0], res.path_y[0], scale, cx, cy)
        canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5,
                           fill=colour, outline="black")

        canvas.create_text(
            10, 28 + 18 * i, anchor="nw", fill=colour,
            text="start ({:+.3f}, {:+.3f})   {} bounces   distance {:.2f}".format(
                res.cfg_snapshot["start_x"], res.cfg_snapshot["start_y"],
                res.total_bounces, res.total_distance),
        )

    controls = tk.Frame(root)
    controls.pack(pady=6)
    tk.Button(controls, text="Close window", command=root.destroy).pack()
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


# =============================================================================
# SIMPLE TERMINAL QUESTIONS (for beginners)
# =============================================================================

def parse_float(text):
    """
    Turn typed text into a float.
    Accepts both 1.1 (English) and 1,1 (Russian-style comma decimal).
    """
    # Remove spaces, then allow comma as decimal point
    cleaned = text.strip().replace(" ", "").replace(",", ".")
    return float(cleaned)


def ask_float(prompt, default):
    """
    Ask for a number; Enter keeps the default.
    If the typed value is bad, explain and ask again (do not crash).
    """
    while True:
        text = input("{} [{}]: ".format(prompt, default)).strip()
        if text == "":
            return float(default)
        try:
            return parse_float(text)
        except ValueError:
            print("  That is not a single number.")
            print("  Examples: 1.1   or   1,1   or   0")
            print("  (Use a DOT or a COMMA for decimals. Do not type two numbers here.)")


def ask_int(prompt, default):
    """Ask for a whole number; Enter keeps the default."""
    while True:
        text = input("{} [{}]: ".format(prompt, default)).strip()
        if text == "":
            return int(default)
        try:
            # Allow "10" or even "10.0" / "10,0"
            return int(round(parse_float(text)))
        except ValueError:
            print("  Please type a whole number, for example: 80")


def ask_str(prompt, default, allowed=None):
    text = input("{} [{}]: ".format(prompt, default)).strip()
    if text == "":
        return default
    if allowed is not None and text not in allowed:
        print("  Invalid. Allowed: {}. Keeping {}.".format(allowed, default))
        return default
    return text


def interactive_edit_config(cfg: Config) -> Config:
    """Type new values in the terminal. Enter = keep current value."""
    print("\n--- Edit settings (press Enter to keep current) ---")
    cfg.board_shape = ask_str(
        "Board shape (rectangle/circle/ellipse/polar)", cfg.board_shape,
        allowed=["rectangle", "circle", "ellipse", "polar"],
    )
    # Side ratio only matters for a rectangular / elliptical board
    if cfg.board_shape == "rectangle":
        cfg.board_ratio = ask_float("Board side ratio width/height", cfg.board_ratio)
        cfg.board_size = ask_float("Board size (half-height)", cfg.board_size)
    elif cfg.board_shape == "circle":
        cfg.board_size = ask_float("Board radius", cfg.board_size)
    elif cfg.board_shape == "ellipse":
        cfg.board_ratio = ask_float("Board radius ratio rx/ry", cfg.board_ratio)
        cfg.board_size = ask_float("Board vertical radius ry", cfg.board_size)
    else:
        # Polar: r(θ) = r0 + a1 cosθ + b1 sinθ + a2 cos2θ + ...
        print("  Polar board: r(θ) = r0 + a1*cosθ + b1*sinθ")
        print("                         + a2*cos2θ + b2*sin2θ")
        print("                         + a3*cos3θ + b3*sin3θ")
        print("  Keep r(θ) >= 0 everywhere (e.g. |a|+|b| <= r0).")
        print("  Tip: r0=1, a1=1 is the CARDIOID - a board proven fully chaotic.")
        cfg.polar_r0 = ask_float("polar r0 (base radius)", cfg.polar_r0)
        cfg.polar_a1 = ask_float("polar a1 (cos θ)", cfg.polar_a1)
        cfg.polar_b1 = ask_float("polar b1 (sin θ)", cfg.polar_b1)
        cfg.polar_a2 = ask_float("polar a2 (cos 2θ)", cfg.polar_a2)
        cfg.polar_b2 = ask_float("polar b2 (sin 2θ)", cfg.polar_b2)
        cfg.polar_a3 = ask_float("polar a3 (cos 3θ)", cfg.polar_a3)
        cfg.polar_b3 = ask_float("polar b3 (sin 3θ)", cfg.polar_b3)

    cfg.obstacle_shape = ask_str(
        "Obstacle shape (circle/ellipse/rectangle/none)", cfg.obstacle_shape,
        allowed=["circle", "ellipse", "rectangle", "none"],
    )
    if cfg.obstacle_shape != "none":
        cfg.obstacle_x = ask_float("Obstacle center x", cfg.obstacle_x)
        cfg.obstacle_y = ask_float("Obstacle center y", cfg.obstacle_y)

        # Ask only for the sizes that this obstacle shape actually uses
        if cfg.obstacle_shape == "circle":
            cfg.obstacle_rx = ask_float("Obstacle radius", cfg.obstacle_rx)
            # ry is unused for a circle; keep it equal so nothing looks weird later
            cfg.obstacle_ry = cfg.obstacle_rx
        elif cfg.obstacle_shape == "ellipse":
            cfg.obstacle_rx = ask_float("Obstacle horizontal radius rx", cfg.obstacle_rx)
            cfg.obstacle_ry = ask_float("Obstacle vertical radius ry", cfg.obstacle_ry)
        else:  # rectangle
            cfg.obstacle_rx = ask_float("Obstacle half-width rx", cfg.obstacle_rx)
            cfg.obstacle_ry = ask_float("Obstacle half-height ry", cfg.obstacle_ry)
    else:
        print("  No obstacle (empty table).")

    cfg.start_x = ask_float("Ball start x", cfg.start_x)
    cfg.start_y = ask_float("Ball start y", cfg.start_y)
    cfg.start_angle_deg = ask_float("Ball start angle (degrees)", cfg.start_angle_deg)

    cfg.max_bounces = ask_int("Max bounces", cfg.max_bounces)
    cfg.max_distance = ask_float("Max path distance", cfg.max_distance)
    print("--- settings updated ---\n")
    return cfg


def linspace(a, b, n):
    """
    Make n numbers evenly spaced from a to b (inclusive).
    (Tiny replacement for numpy.linspace - no numpy needed.)
    """
    if n <= 1:
        return [float(a)]
    step = (b - a) / (n - 1)
    return [a + i * step for i in range(n)]


def run_many_angle_scan(cfg: Config, angles, start_trial_id=1):
    """
    Run many trials that differ ONLY by start angle.
    Great for seeing chaos: nearby angles -> different paths.
    """
    results = []
    for i, ang in enumerate(angles):
        trial_cfg = copy.deepcopy(cfg)
        trial_cfg.start_angle_deg = float(ang)
        trial_cfg.show_plot = False  # do not open dozens of windows
        tid = start_trial_id + i
        print("Running trial {} with angle={} deg ...".format(tid, ang))
        result = run_trial(trial_cfg, trial_id=tid)
        results.append(result)
        print_summary_table(result)
    return results


# =============================================================================
# SALI CHAOS ANALYSIS  (board "chaoticness")
# =============================================================================
# Literature (Skokos 2001; Skokos et al. nlin/0210053, nlin/0404058, nlin/0703037;
# Skokos & Manos arXiv:1412.7401):
#
#   SALI(t) = min( ||w1_hat + w2_hat|| , ||w1_hat - w2_hat|| )
#
# For the billiard bounce map (a 2D symplectic map):
#   - chaotic orbits:  SALI ~ exp(-2 * lambda * n)  -> drops to machine zero
#   - regular/periodic: SALI ~ n^(-2)               -> slow power-law decay
#
# Practical defaults used below (standard in the papers above):
#   - n_bounces   = 500   (after this, regular SALI ~ 4e-6; chaotic << 1e-8)
#   - threshold   = 1e-8  (orbit called chaotic if SALI stays <= threshold)
#
# Why "stays" matters (persistence):
#   A REGULAR orbit that passes close to an unstable periodic orbit (e.g. the
#   major-axis orbit of an ellipse, or any separatrix) gets its two deviation
#   vectors transiently squeezed together while it lingers near that unstable
#   point. SALI then DIPS below the threshold for a few bounces and RECOVERS.
#   A genuinely chaotic orbit instead collapses to machine zero and never
#   recovers. So a single dip is not proof of chaos: we require SALI to stay
#   below the threshold for SALI_DEFAULT_PERSIST consecutive bounces.
#   Without this, an empty ellipse (an integrable board!) scores ~5% chaotic
#   purely from those transient dips.
#   - n_trials    = 360   (angles every 1 deg on [0, 360); ~+/-2.5% SE on the
#                          chaotic fraction — better than 200, enough for a
#                          board summary without a full phase-space grid)
#
# Chaoticness of a board (fixed start position) =
#   (number of start angles classified chaotic) / (number of successful trials)

# Defaults chosen from the literature review above
SALI_DEFAULT_TRIALS = 360
SALI_DEFAULT_BOUNCES = 500
SALI_DEFAULT_THRESHOLD = 1e-8
SALI_JACOBIAN_EPS = 1e-8

# How many CONSECUTIVE bounces SALI must stay <= threshold before we accept
# that the orbit is chaotic (see the persistence note above).
SALI_DEFAULT_PERSIST = 20

# Fraction of one angle step by which the full-circle grid is shifted.
#
# Why shift at all: a grid starting exactly at 0 deg samples 0, 90, 180 and
# 270 deg, which are precisely the symmetry directions where special orbits
# live (bouncing-ball orbits in the channel beside a centred scatterer, the
# major-axis orbit of an ellipse, ...). Those families have measure zero, so a
# correct survey should almost never land on them, but an aligned grid hits all
# four every time. That alone made the proven-ergodic Sinai billiard score
# 0.978 instead of 1.000. Shifting the grid off the axes fixes it.
# Set to 0.0 to get the old exactly-aligned grid back.
SALI_DEFAULT_ANGLE_OFFSET_FRAC = 0.37

# A board survey needs BOTH numbers, so they are measured together:
#   chaoticness = mean chaotic fraction over start points
#   spread      = HALF of (max - min) over those start points
# One start point only samples a 1D slice of the 2D phase space, so its score
# alone cannot tell "this board is 65% chaotic everywhere" apart from "this
# board is 40% chaotic here and 98% chaotic over there". The spread is what
# distinguishes them, and on measured boards it reached 0.29.
#
# Why HALF the width: it is then a plus/minus, so the range the board actually
# covers is just chaoticness +/- spread instead of needing a division first.
# Total orbits per survey = SALI_DEFAULT_STARTS * SALI_DEFAULT_ANGLES.
SALI_DEFAULT_STARTS = 8
SALI_DEFAULT_ANGLES = 90


@dataclass
class SaliOrbitResult:
    """SALI classification of one start angle."""
    angle_deg: float
    final_sali: float
    n_bounces_done: int
    label: str          # "chaotic", "regular", or "failed"


@dataclass
class ChaoticnessResult:
    """Board chaoticness from a multi-angle SALI survey."""
    n_trials: int
    n_chaotic: int
    n_regular: int
    n_failed: int
    chaotic_fraction: float   # the "chaoticness" score in [0, 1]
    regular_fraction: float
    n_bounces: int
    threshold: float
    persist: int              # consecutive low-SALI bounces required
    start_x: float
    start_y: float
    orbits: list              # list of SaliOrbitResult


def one_bounce_step(x, y, vx, vy, cfg: Config):
    """
    Advance the ball through exactly one free-flight + elastic bounce.
    Returns (x, y, vx, vy, nx, ny) just after the bounce nudge, or None.
    (nx, ny) is the inward unit normal of the surface that was hit.
    """
    board = next_board_hit(x, y, vx, vy, cfg)
    obst = next_obstacle_hit(x, y, vx, vy, cfg)

    choice = None
    if board is not None:
        choice = ("board",) + board
    if obst is not None:
        if choice is None or obst[0] < choice[1]:
            choice = ("obstacle",) + obst
    if choice is None:
        return None

    _hit_what, t, nx, ny = choice
    x = x + t * vx
    y = y + t * vy
    vx, vy = reflect(vx, vy, nx, ny)
    nudge = max(cfg.epsilon, 1e-8)
    x = x + nudge * nx
    y = y + nudge * ny
    return x, y, vx, vy, nx, ny


def _wrap_angle_diff(d):
    """Map an angle difference into (-pi, pi]."""
    return (d + math.pi) % (2.0 * math.pi) - math.pi


def _unit_tangent(nx, ny):
    """Unit tangent obtained by rotating the inward normal by +90 deg."""
    return -ny, nx


def _bounce_map_state(x, y, theta, cfg: Config):
    """
    One bounce-map step. State is carried as (x, y, theta) with theta in radians.
    Returns (x', y', theta', nx', ny') or None.
    """
    vx = math.cos(theta)
    vy = math.sin(theta)
    stepped = one_bounce_step(x, y, vx, vy, cfg)
    if stepped is None:
        return None
    x2, y2, vx2, vy2, nx2, ny2 = stepped
    return x2, y2, math.atan2(vy2, vx2), nx2, ny2


def _matvec2(J, w):
    """Multiply 2x2 matrix J (list of rows) by vector w."""
    return [
        J[0][0] * w[0] + J[0][1] * w[1],
        J[1][0] * w[0] + J[1][1] * w[1],
    ]


def _norm2(w):
    return math.sqrt(w[0] * w[0] + w[1] * w[1])


def _normalize2(w):
    n = _norm2(w)
    if n < 1e-30:
        return None
    return [w[0] / n, w[1] / n]


def _sali_of(w1, w2):
    """SALI = min(||w1+w2||, ||w1-w2||) for unit vectors w1, w2."""
    d_plus = _norm2([w1[0] + w2[0], w1[1] + w2[1]])
    d_minus = _norm2([w1[0] - w2[0], w1[1] - w2[1]])
    return min(d_plus, d_minus)


def _section_delta(state_a, state_b):
    """
    Difference of two post-bounce states in Birkhoff-like 2D coords (s, theta):
      ds     = tangential displacement at B's surface
      dtheta = wrapped angle difference
    state = (x, y, theta, nx, ny)
    """
    xa, ya, tha, _nxa, _nya = state_a
    xb, yb, thb, nxb, nyb = state_b
    tx, ty = _unit_tangent(nxb, nyb)
    ds = (xa - xb) * tx + (ya - yb) * ty
    dth = _wrap_angle_diff(tha - thb)
    return ds, dth


def _finite_diff_jacobian_2d(x, y, theta, nx, ny, cfg: Config, eps=SALI_JACOBIAN_EPS):
    """
    2x2 Jacobian of the bounce map in local section coordinates (s, theta).

    Columns:
      0 = perturb position along the current boundary tangent
      1 = perturb the outgoing angle
    Rows measure (ds', dtheta') at the next bounce.

    Returns (next_x, next_y, next_theta, next_nx, next_ny, J) or None.
    """
    f0 = _bounce_map_state(x, y, theta, cfg)
    if f0 is None:
        return None

    tx, ty = _unit_tangent(nx, ny)

    # Column 0: move along tangent on the current section
    f_s = _bounce_map_state(x + eps * tx, y + eps * ty, theta, cfg)
    if f_s is None:
        return None
    ds0, dth0 = _section_delta(f_s, f0)

    # Column 1: change outgoing angle only
    f_th = _bounce_map_state(x, y, theta + eps, cfg)
    if f_th is None:
        return None
    ds1, dth1 = _section_delta(f_th, f0)

    J = [
        [ds0 / eps, ds1 / eps],
        [dth0 / eps, dth1 / eps],
    ]
    x2, y2, th2, nx2, ny2 = f0
    return x2, y2, th2, nx2, ny2, J


def compute_sali_for_angle(
    cfg: Config,
    angle_deg,
    n_bounces=SALI_DEFAULT_BOUNCES,
    threshold=SALI_DEFAULT_THRESHOLD,
    persist=SALI_DEFAULT_PERSIST,
):
    """
    Classify one start angle with SALI on the billiard bounce map.

    1) Fly from the interior start point to the first bounce (Poincare section).
    2) Evolve two orthonormal deviation vectors with the 2x2 section Jacobian
       for up to n_bounces collisions (Skokos algorithm).
    3) Label chaotic only if SALI STAYS <= threshold for `persist` consecutive
       bounces (a transient dip near an unstable orbit is not chaos - see the
       persistence note in the section header), else regular/periodic.

    Returns a SaliOrbitResult.
    """
    validate_start(cfg)
    x = float(cfg.start_x)
    y = float(cfg.start_y)
    theta = math.radians(float(angle_deg))

    # Land on the bounce section before measuring SALI
    first = _bounce_map_state(x, y, theta, cfg)
    if first is None:
        return SaliOrbitResult(
            angle_deg=float(angle_deg),
            final_sali=float("nan"),
            n_bounces_done=0,
            label="failed",
        )
    x, y, theta, nx, ny = first

    # Two initially orthonormal unit deviation vectors in (s, theta)
    # (Skokos: orthogonal start gives the largest possible initial SALI = sqrt(2))
    w1 = [1.0, 0.0]
    w2 = [0.0, 1.0]
    sali = _sali_of(w1, w2)
    done = 0
    # Length of the current unbroken streak of SALI <= threshold
    low_streak = 0
    persist = max(1, int(persist))

    for _ in range(int(n_bounces)):
        mapped = _finite_diff_jacobian_2d(x, y, theta, nx, ny, cfg)
        if mapped is None:
            return SaliOrbitResult(
                angle_deg=float(angle_deg),
                final_sali=sali,
                n_bounces_done=done,
                label="failed",
            )
        x, y, theta, nx, ny, J = mapped
        done += 1

        w1 = _normalize2(_matvec2(J, w1))
        w2 = _normalize2(_matvec2(J, w2))
        if w1 is None or w2 is None:
            return SaliOrbitResult(
                angle_deg=float(angle_deg),
                final_sali=0.0,
                n_bounces_done=done,
                label="chaotic",
            )

        sali = _sali_of(w1, w2)
        if sali <= threshold:
            low_streak += 1
            # Sustained collapse: chaotic orbits never climb back out
            if low_streak >= persist:
                return SaliOrbitResult(
                    angle_deg=float(angle_deg),
                    final_sali=sali,
                    n_bounces_done=done,
                    label="chaotic",
                )
        else:
            # SALI recovered, so that dip was only a transient squeeze
            low_streak = 0

    return SaliOrbitResult(
        angle_deg=float(angle_deg),
        final_sali=sali,
        n_bounces_done=done,
        label="regular",
    )


def measure_board_chaoticness(
    cfg: Config,
    n_trials=SALI_DEFAULT_TRIALS,
    n_bounces=SALI_DEFAULT_BOUNCES,
    threshold=SALI_DEFAULT_THRESHOLD,
    persist=SALI_DEFAULT_PERSIST,
    angle_start_deg=0.0,
    angle_end_deg=360.0,
    angle_offset_frac=SALI_DEFAULT_ANGLE_OFFSET_FRAC,
    verbose=True,
):
    """
    Estimate how chaotic the current board is at cfg.start_x / cfg.start_y.

    Runs n_trials orbits at evenly spaced start angles, classifies each with
    SALI, and returns

        chaoticness = n_chaotic / (n_chaotic + n_regular)

    (failed orbits are reported but excluded from the fraction).

    NOTE: this is chaoticness AT ONE START POINT, and is only the inner loop of
    the board survey. Call measure_board_chaos() instead for the board-level
    chaoticness and spread, because on a mixed board the answer depends
    strongly on where the ball starts.

    Defaults (see module comments): n_trials=360, n_bounces=500, threshold=1e-8,
    persist=20, angle_offset_frac=0.37.
    """
    n_trials = max(1, int(n_trials))
    # Use half-open angle grid so 0 and 360 are not duplicated when scanning a full turn
    if n_trials == 1:
        angles = [float(angle_start_deg)]
    else:
        span = float(angle_end_deg) - float(angle_start_deg)
        # For a full 360 deg sweep, sample n points in [start, start+360)
        if abs(span - 360.0) < 1e-9:
            step = span / n_trials
            # Nudge the periodic grid off the symmetry axes (see
            # SALI_DEFAULT_ANGLE_OFFSET_FRAC). Harmless here because the grid
            # wraps; an explicit sub-range below is left exactly as asked for.
            shift = step * float(angle_offset_frac)
            angles = [angle_start_deg + shift + step * i for i in range(n_trials)]
        else:
            angles = linspace(angle_start_deg, angle_end_deg, n_trials)

    orbits = []
    n_chaotic = 0
    n_regular = 0
    n_failed = 0

    if verbose:
        print(
            "SALI chaoticness: {} angles, {} bounces/orbit, threshold={:g}, "
            "persist={}".format(n_trials, n_bounces, threshold, persist)
        )
        print(
            "  start=({:.4g}, {:.4g}), board={}, obstacle={}".format(
                cfg.start_x, cfg.start_y, cfg.board_shape, cfg.obstacle_shape
            )
        )

    for i, ang in enumerate(angles):
        orbit = compute_sali_for_angle(
            cfg, ang, n_bounces=n_bounces, threshold=threshold, persist=persist
        )
        orbits.append(orbit)
        if orbit.label == "chaotic":
            n_chaotic += 1
        elif orbit.label == "regular":
            n_regular += 1
        else:
            n_failed += 1

        if verbose and ((i + 1) % max(1, n_trials // 10) == 0 or i + 1 == n_trials):
            print(
                "  ... {}/{}  chaotic={} regular={} failed={}".format(
                    i + 1, n_trials, n_chaotic, n_regular, n_failed
                )
            )

    classified = n_chaotic + n_regular
    chaotic_fraction = (n_chaotic / classified) if classified > 0 else 0.0
    regular_fraction = (n_regular / classified) if classified > 0 else 0.0

    return ChaoticnessResult(
        n_trials=n_trials,
        n_chaotic=n_chaotic,
        n_regular=n_regular,
        n_failed=n_failed,
        chaotic_fraction=chaotic_fraction,
        regular_fraction=regular_fraction,
        n_bounces=int(n_bounces),
        threshold=float(threshold),
        persist=max(1, int(persist)),
        start_x=float(cfg.start_x),
        start_y=float(cfg.start_y),
        orbits=orbits,
    )


@dataclass
class StartScore:
    """Chaoticness measured at one start point."""
    x: float
    y: float
    chaotic_fraction: float
    n_chaotic: int
    n_regular: int
    n_failed: int


@dataclass
class BoardChaosResult:
    """
    One board survey holding BOTH headline numbers:
      chaoticness (mean_fraction) and spread.
    """
    board_shape: str
    obstacle_shape: str
    n_starts: int
    n_angles: int             # angles per start point
    n_bounces: int
    threshold: float
    persist: int
    mean_fraction: float      # the board chaoticness score
    min_fraction: float
    max_fraction: float
    spread: float             # (max - min)/2, a plus/minus; large => mixed
    total_chaotic: int
    total_regular: int
    total_failed: int
    per_start: list           # list of StartScore

    @property
    def is_mixed(self) -> bool:
        """True when regular and chaotic regions coexist on this board."""
        return self.spread >= 0.025   # half-width, so half of the old 0.05


def sample_interior_points(cfg: Config, n_points, seed=12345):
    """
    Pick n_points legal ball positions spread uniformly BY AREA over the board.

    Uniform-by-area matters: the chaotic fraction is meant to approximate a
    phase-space measure, so start points must not be bunched up anywhere.
    Rejection sampling in the bounding box gives exactly that.
    """
    hw, hh = board_world_half_size(cfg)
    # Small deterministic generator so runs are repeatable without importing random
    state = int(seed) & 0xFFFFFFFF

    def next_uniform():
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state / float(0x7FFFFFFF)

    points = []
    attempts = 0
    max_attempts = 20000 * max(1, int(n_points))
    while len(points) < int(n_points) and attempts < max_attempts:
        attempts += 1
        x = (2.0 * next_uniform() - 1.0) * hw
        y = (2.0 * next_uniform() - 1.0) * hh
        if not point_inside_board(x, y, cfg):
            continue
        if point_inside_obstacle(x, y, cfg):
            continue
        points.append((x, y))
    return points


def measure_board_chaos(
    cfg: Config,
    n_starts=SALI_DEFAULT_STARTS,
    n_angles=SALI_DEFAULT_ANGLES,
    n_bounces=SALI_DEFAULT_BOUNCES,
    threshold=SALI_DEFAULT_THRESHOLD,
    persist=SALI_DEFAULT_PERSIST,
    seed=12345,
    verbose=True,
):
    """
    Survey a board and return CHAOTICNESS and SPREAD together.

    Sweeps n_angles start directions from each of n_starts start points drawn
    uniformly by area, then reports:

      chaoticness = mean chaotic fraction over the start points
      spread      = HALF of (max - min) over the start points, i.e. a +/-

    Both are needed. Chaoticness alone cannot distinguish a board that is
    uniformly 65% chaotic from one that is 40% chaotic in one region and 98% in
    another; the spread separates those cases. A spread near 0 means the board
    behaves the same everywhere (integrable, or fully chaotic); a large spread
    means regular and chaotic regions coexist and no single number describes it.

    Setting n_starts=1 reduces this to a single-point measurement, in which
    case spread is 0 by construction and carries no information.
    """
    points = sample_interior_points(cfg, n_starts, seed=seed)
    if not points:
        raise ValueError(
            "Could not find any legal start point inside this board. "
            "Check the board size and the obstacle."
        )

    if verbose:
        print("Board chaos survey: {} start points x {} angles x {} bounces "
              "({} orbits)".format(len(points), n_angles, n_bounces,
                                   len(points) * int(n_angles)))

    per_start = []
    scratch = copy.deepcopy(cfg)
    for i, (sx, sy) in enumerate(points):
        scratch.start_x = sx
        scratch.start_y = sy
        r = measure_board_chaoticness(
            scratch, n_trials=n_angles, n_bounces=n_bounces,
            threshold=threshold, persist=persist, verbose=False,
        )
        per_start.append(StartScore(
            x=sx, y=sy, chaotic_fraction=r.chaotic_fraction,
            n_chaotic=r.n_chaotic, n_regular=r.n_regular, n_failed=r.n_failed,
        ))
        if verbose:
            print("  start {:>2}/{}: ({:+.3f}, {:+.3f}) -> {:.3f}".format(
                i + 1, len(points), sx, sy, r.chaotic_fraction))

    fracs = [s.chaotic_fraction for s in per_start]
    return BoardChaosResult(
        board_shape=str(cfg.board_shape),
        obstacle_shape=str(cfg.obstacle_shape),
        n_starts=len(points),
        n_angles=int(n_angles),
        n_bounces=int(n_bounces),
        threshold=float(threshold),
        persist=max(1, int(persist)),
        mean_fraction=sum(fracs) / len(fracs),
        min_fraction=min(fracs),
        max_fraction=max(fracs),
        spread=0.5 * (max(fracs) - min(fracs)),
        total_chaotic=sum(s.n_chaotic for s in per_start),
        total_regular=sum(s.n_regular for s in per_start),
        total_failed=sum(s.n_failed for s in per_start),
        per_start=per_start,
    )


def print_board_chaos_report(result: BoardChaosResult):
    """
    Print the single board survey: chaoticness AND spread, plus the per-start
    detail they come from. TAB-separated so it pastes into Google Sheets.
    """
    print("\n--- SALI board chaos survey ---")
    print("board_shape\t{}".format(result.board_shape))
    print("obstacle_shape\t{}".format(result.obstacle_shape))
    print("n_starts\t{}".format(result.n_starts))
    print("n_angles_per_start\t{}".format(result.n_angles))
    print("n_bounces\t{}".format(result.n_bounces))
    print("threshold\t{:g}".format(result.threshold))
    print("persist\t{}".format(result.persist))
    print("orbits_total\t{}".format(result.n_starts * result.n_angles))
    print("orbits_chaotic\t{}".format(result.total_chaotic))
    print("orbits_regular\t{}".format(result.total_regular))
    print("orbits_failed\t{}".format(result.total_failed))

    # The two headline numbers
    print("CHAOTICNESS\t{:.6f}\t({:.2f}%)".format(
        result.mean_fraction, 100.0 * result.mean_fraction))
    print("SPREAD_PLUSMINUS\t{:.6f}\t(half of max-min)".format(result.spread))
    print("min_over_starts\t{:.6f}".format(result.min_fraction))
    print("max_over_starts\t{:.6f}".format(result.max_fraction))

    if result.n_starts < 2:
        print("reading\tsingle start point - spread carries no information")
    elif not result.is_mixed:
        if result.mean_fraction <= 0.02:
            kind = "regular everywhere (looks integrable)"
        elif result.mean_fraction >= 0.98:
            kind = "chaotic everywhere (looks ergodic)"
        else:
            kind = "the same everywhere"
        print("reading\tUNIFORM phase space: {}".format(kind))
    else:
        print("reading\tMIXED phase space: regular and chaotic regions coexist,"
              " so the chaoticness alone is misleading here")

    print("\nper start point:")
    print("start_x\tstart_y\tchaotic_fraction\tchaotic\tregular\tfailed")
    for s in result.per_start:
        print("{:.6f}\t{:.6f}\t{:.6f}\t{}\t{}\t{}".format(
            s.x, s.y, s.chaotic_fraction, s.n_chaotic, s.n_regular, s.n_failed))


def print_chaoticness_report(result: ChaoticnessResult):
    """Print a short chaoticness summary (TAB-friendly)."""
    print("\n--- SALI board chaoticness ---")
    print("start_x\t{}".format(result.start_x))
    print("start_y\t{}".format(result.start_y))
    print("n_trials\t{}".format(result.n_trials))
    print("n_bounces\t{}".format(result.n_bounces))
    print("threshold\t{:g}".format(result.threshold))
    print("persist\t{}".format(result.persist))
    print("n_chaotic\t{}".format(result.n_chaotic))
    print("n_regular\t{}".format(result.n_regular))
    print("n_failed\t{}".format(result.n_failed))
    print("chaotic_fraction\t{:.6f}".format(result.chaotic_fraction))
    print("regular_fraction\t{:.6f}".format(result.regular_fraction))
    print(
        "chaoticness\t{:.2f}%  ({} chaotic / {} classified)".format(
            100.0 * result.chaotic_fraction,
            result.n_chaotic,
            result.n_chaotic + result.n_regular,
        )
    )


# =============================================================================
# MAIN MENU
# =============================================================================

def main():
    cfg = copy.deepcopy(CFG)
    next_trial_id = 1
    all_results = []

    print("=" * 60)
    print("  SINAI BILLIARD - beginner interactive runner")
    print("=" * 60)
    print("Commands:")
    print("  1  = edit settings (board, obstacle, ball, length)")
    print("  2  = run ONE trial (animated window + tables + auto-save CSV)")
    print("  3  = run an ANGLE SCAN (many angles, chaos demo)")
    print("  4  = re-save all trials to CSV (overwrites, for Google Sheets)")
    print("  5  = print current settings")
    print("  6  = measure board CHAOTICNESS + SPREAD (SALI survey)")
    print("  7  = compare START POSITIONS (several paths on one picture)")
    print("  q  = quit")
    print("=" * 60)

    while True:
        choice = input("\nChoose command [1/2/3/4/5/6/7/q]: ").strip().lower()

        if choice == "q":
            print("Bye!")
            break

        elif choice == "1":
            cfg = interactive_edit_config(cfg)

        elif choice == "2":
            try:
                result = run_trial(cfg, trial_id=next_trial_id)
            except ValueError as err:
                print("ERROR:", err)
                continue

            all_results.append(result)
            print_summary_table(result)
            print_bounce_table(result)
            # Auto-save after every trial so you always have a clean CSV
            if cfg.save_csv_file:
                save_results_to_csv(all_results, cfg.save_csv_file)
            plot_trial(result, cfg)
            next_trial_id += 1

        elif choice == "3":
            print("Angle scan: many trials with different start angles.")
            a0 = ask_float("First angle (degrees)", cfg.start_angle_deg)
            a1 = ask_float("Last angle (degrees)", cfg.start_angle_deg + 5.0)
            n = ask_int("How many angles", 6)
            angles = linspace(a0, a1, n)
            results = run_many_angle_scan(cfg, angles, start_trial_id=next_trial_id)
            all_results.extend(results)
            next_trial_id += len(results)
            if cfg.save_csv_file:
                # Save the WHOLE session (overwrites), so no duplicates
                save_results_to_csv(all_results, cfg.save_csv_file)
            print("Angle scan done.")

        elif choice == "4":
            if not all_results:
                print("No trials yet. Run command 2 or 3 first.")
            else:
                save_results_to_csv(all_results, cfg.save_csv_file)

        elif choice == "5":
            print("\nCurrent settings:")
            for name, value in cfg.__dict__.items():
                print("  {}: {}".format(name, value))

        elif choice == "6":
            print("SALI board chaos survey. Reports BOTH numbers:")
            print("  CHAOTICNESS = how chaotic the board is on average")
            print("  SPREAD      = how much that varies across the board,")
            print("                given as a +/- (near 0 = same everywhere)")
            ns = ask_int("How many start points", SALI_DEFAULT_STARTS)
            n = ask_int("Angles per start point", SALI_DEFAULT_ANGLES)
            nb = ask_int("Bounces per orbit (SALI iterations)", SALI_DEFAULT_BOUNCES)
            try:
                chaos = measure_board_chaos(
                    cfg, n_starts=ns, n_angles=n, n_bounces=nb, verbose=True
                )
            except ValueError as err:
                print("ERROR:", err)
                continue
            print_board_chaos_report(chaos)

        elif choice == "7":
            print("Compare START POSITIONS: same angle, several places on the board.")
            npos = ask_int("How many start positions", 5)
            try:
                multi_results = run_multi_start_trial(
                    cfg, n_points=npos, start_trial_id=next_trial_id, verbose=True
                )
            except ValueError as err:
                print("ERROR:", err)
                continue
            all_results.extend(multi_results)
            next_trial_id += len(multi_results)
            if cfg.save_csv_file:
                save_results_to_csv(all_results, cfg.save_csv_file)
            plot_multi_start(multi_results, cfg)

        else:
            print("Unknown command. Use 1, 2, 3, 4, 5, 6, 7, 8, or q.")


# Run the menu only when you execute this file directly:
#     py sinai_billiard.py
if __name__ == "__main__":
    main()
