"""
Run a chaoticness STUDY - one board, one parameter swept - and write the
results straight into a spreadsheet that Google Sheets can open.

Each study becomes its own PAGE (worksheet) in one .xlsx file, so a workbook
holds several unrelated investigations side by side:

    page "circle_sin1"    r = 1 + a sin(theta),   a increasing from 0
    page "limacon"        r = 1 + a cos(theta),   a: circle -> cardioid
    page "ellipse_dent"   ellipse with a growing dent
    page "stadium_gamma"  stadium, straight section growing
    page "Legend"         what every column means, and the literature anchors

Run it:

    py chaos_studies.py                       list the studies
    py chaos_studies.py limacon               run one study
    py chaos_studies.py limacon circle_sin1   run several, one page each
    py chaos_studies.py all --quick           everything, coarse and fast

Then drag the .xlsx into Google Drive and open it: the pages come through as
separate tabs. Numbers are written as real numbers, so charts work directly.

Chaos is measured with analyse_chaos_phase_space, i.e. sampled uniformly over
the whole phase space rather than from a single start point. On a mixed board
the single-point figure can be several times too high, and mixed boards are the
interesting ones here.
"""

import copy
import datetime
import math
import os
import sys
import time

import sinai_billiard as sb


# =============================================================================
# SHORT VERDICTS
# =============================================================================
# Two independent questions, so two columns:
#
#   regime   - HOW MUCH of the phase space is chaotic  (from SALI)
#   strength - HOW HARD the chaotic part stretches     (from lambda)
#
# A board can be "mixed" yet "violent", or "chaotic" yet only "slightly" so;
# neither column implies the other, which is the whole reason both are kept.

REGIME_REGULAR_MAX = 0.02      # at or below this fraction: call it regular
REGIME_CHAOTIC_MIN = 0.98      # at or above this fraction: call it chaotic


def chaos_regime(fraction: float, n_chaotic: int) -> str:
    """
    "regular" / "mixed" / "chaotic" from the chaotic fraction of phase space.

    The word is "regular", not "periodic". In a circle or an ellipse almost
    every orbit never closes on itself - it winds forever on an invariant
    curve, which is QUASI-periodic. "Regular" covers both that and the genuinely
    periodic orbits; "periodic" alone would be false for nearly all of them.
    """
    if n_chaotic == 0 or fraction <= REGIME_REGULAR_MAX:
        return "regular"
    if fraction >= REGIME_CHAOTIC_MIN:
        return "chaotic"
    return "mixed"


def chaos_strength(exponent: float) -> str:
    """
    "no chaos" / "slightly chaotic" / ... / "violent chaos" from lambda.

    Delegates to sinai_billiard.lyapunov_band so the wording and the
    thresholds stay identical to everything else the program prints.
    """
    if exponent != exponent:        # NaN: nothing chaotic was found to average
        return "no chaos"
    return sb.lyapunov_band(exponent)


# =============================================================================
# GEOMETRY NEEDED FOR THE CONVENTION-SAFE COLUMN
# =============================================================================

def board_area(cfg) -> float:
    """Area enclosed by the wall, by the shoelace formula on a dense polyline."""
    pts = sb.board_boundary_polyline(cfg)
    total = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        total += x0 * y1 - x1 * y0
    return abs(total) * 0.5


def obstacle_area_and_perimeter(cfg):
    """(area, perimeter) of the obstacle, or (0, 0) when there is none."""
    if cfg.obstacle_shape == "none":
        return 0.0, 0.0
    rx, ry = cfg.obstacle_rx, cfg.obstacle_ry
    if cfg.obstacle_shape == "circle":
        return math.pi * rx * rx, 2.0 * math.pi * rx
    if cfg.obstacle_shape == "ellipse":
        # Ramanujan's approximation for the ellipse perimeter
        h = ((rx - ry) ** 2) / ((rx + ry) ** 2) if (rx + ry) > 0 else 0.0
        per = math.pi * (rx + ry) * (1.0 + 3.0 * h / (10.0 + math.sqrt(4.0 - 3.0 * h)))
        return math.pi * rx * ry, per
    # rectangle: rx, ry are HALF-widths
    return 4.0 * rx * ry, 4.0 * (rx + ry)


def mean_free_path(cfg) -> float:
    """
    Average distance between collisions, <l> = pi * (free area) / (total wall).

    This is exact for any 2D billiard and it is what converts between the two
    conventions in the literature:

        lambda_per_collision = lambda_per_unit_length * <l>

    Getting this backwards is the single easiest way to be wrong by a factor of
    two: Benettin & Strelcyn's famous stadium value 0.43 is per unit LENGTH,
    which is 0.94 per collision.
    """
    free_area = board_area(cfg)
    total_wall = sb.boundary_perimeter(cfg)
    obs_area, obs_per = obstacle_area_and_perimeter(cfg)
    free_area -= obs_area
    total_wall += obs_per
    if total_wall <= 0 or free_area <= 0:
        return float("nan")
    return math.pi * free_area / total_wall


# =============================================================================
# SETTING THE SWEPT PARAMETER
# =============================================================================
# Human-readable labels, so a page header says what was actually varied
# instead of just an attribute name.

PARAM_LABELS = {
    "polar_r0": "r0  (base radius)",
    "polar_a1": "a1  (coefficient of cos theta)",
    "polar_b1": "a  (coefficient of sin theta)",
    "polar_a2": "a2  (coefficient of cos 2theta)",
    "polar_b2": "b2  (coefficient of sin 2theta)",
    "polar_a3": "a3  (coefficient of cos 3theta)",
    "polar_b3": "b3  (coefficient of sin 3theta)",
    "board_ratio": "board ratio  (rx / ry)",
    "board_size": "board size",
    "ellipse_bump": "dent size  (eps in 1 + eps cos n theta)",
    "ellipse_bump_n": "dent harmonic n",
    "stadium_half_length": "a  (half-length of the straight section)",
    "stadium_curve": "c  (level of curving, 1 = semicircular caps)",
    "obstacle_r": "obstacle radius",
    "obstacle_rx": "obstacle rx",
    "obstacle_ry": "obstacle ry",
}


def set_param(cfg, name: str, value):
    """
    Set one swept parameter on a config.

    "obstacle_r" is an alias that moves rx and ry together, which is what a
    circular scatterer needs - setting only rx would silently leave an ellipse.
    """
    if name == "obstacle_r":
        cfg.obstacle_rx = value
        cfg.obstacle_ry = value
        return
    if not hasattr(cfg, name):
        raise ValueError(
            "Config has no parameter '{}'. Known sweepable names include: {}"
            .format(name, ", ".join(sorted(PARAM_LABELS)))
        )
    setattr(cfg, name, value)


def ensure_valid_start(cfg):
    """
    Make sure cfg's start point is legal after the geometry changed.

    The phase-space survey builds its own start states along the wall, so this
    only has to satisfy validate_start. But it does have to: deforming a board
    can easily leave the old start point outside the new wall, which would
    abort the sweep partway through.
    """
    if (sb.point_inside_board(cfg.start_x, cfg.start_y, cfg)
            and not sb.point_inside_obstacle(cfg.start_x, cfg.start_y, cfg)):
        return cfg
    for x, y in sb.spread_start_points(cfg, n_points=12):
        cfg.start_x, cfg.start_y = x, y
        return cfg
    raise ValueError("No valid start point could be found on this board.")


# =============================================================================
# ONE STUDY = ONE PAGE
# =============================================================================

COLUMNS = [
    # (header, width, note for the Legend page)
    ("N", 5, "Experiment number within this page."),
    ("PARAM", 30, "The parameter being varied. Header says which one."),
    ("SALI_fraction", 14,
     "SALI: fraction of PHASE SPACE that is chaotic, 0..1. The 'how much'."),
    ("regime", 10,
     "Short answer from SALI_fraction: regular / mixed / chaotic. "
     "'regular' means no chaos found (periodic OR quasi-periodic motion)."),
    ("lambda", 11,
     "Lyapunov exponent per COLLISION, averaged over the chaotic orbits only. "
     "The 'how hard'. Blank when nothing chaotic was found."),
    ("lambda_err", 11,
     "Standard error of that mean. Differences smaller than this are noise."),
    ("L", 10,
     "Lyapunov NUMBER, L = exp(lambda). Factor two nearby paths separate by "
     "each bounce. Same information as lambda, multiplicative form."),
    ("strength", 18,
     "Short answer from lambda: no chaos / slightly chaotic / moderate chaos / "
     "strong chaos / violent chaos."),
    ("lambda_per_length", 17,
     "lambda divided by the mean free path, i.e. per unit distance travelled "
     "instead of per collision. Some papers quote THIS convention - compare "
     "like with like."),
    ("mean_free_path", 14,
     "Average distance between collisions, pi*Area/Perimeter. The conversion "
     "factor between the two lambda columns."),
    ("KS_estimate", 12,
     "SALI_fraction * lambda. Entropy-like: high only when the board is both "
     "widely AND strongly chaotic."),
    ("n_chaotic", 10, "Chaotic samples, so the fraction can be audited."),
    ("n_regular", 10, "Regular samples."),
    ("n_failed", 9, "Samples that could not be classified."),
    ("grid_s", 8, "Sample points along the wall."),
    ("grid_p", 8, "Sample points in launch angle."),
    ("bounces", 9, "Collisions per orbit. Short runs read slightly positive "
                   "lambda even for regular orbits."),
    ("wall_length", 12, "Perimeter of the wall, for reference."),
    ("seconds", 9, "Wall-clock time for this row."),
]


class Study:
    """One page: a title, the parameter varied, and the measured rows."""

    def __init__(self, key, title, board_note, param_name, param_label, rows,
                 n_s, n_p, n_bounces):
        self.key = key
        self.title = title
        self.board_note = board_note
        self.param_name = param_name
        self.param_label = param_label
        self.rows = rows
        self.n_s = n_s
        self.n_p = n_p
        self.n_bounces = n_bounces


def run_study(spec, n_s=14, n_p=11, n_bounces=300, verbose=True):
    """
    Sweep one parameter over one board and collect a row per value.

    `spec` is a dict with keys: key, title, board_note, make_cfg, param,
    values. Returns a Study.
    """
    param = spec["param"]
    label = PARAM_LABELS.get(param, param)
    rows = []

    if verbose:
        print("\n" + "=" * 68)
        print("STUDY: {}".format(spec["title"]))
        print("  board   : {}".format(spec["board_note"]))
        print("  varying : {}".format(label))
        print("  grid    : {} x {} states, {} bounces each".format(
            n_s, n_p, n_bounces))
        print("=" * 68)
        print("{:>3}  {:>12}  {:>8}  {:>9}  {:>8}  {:>8}  {}".format(
            "N", label.split()[0], "SALI", "regime", "lambda", "L", "strength"))
        sys.stdout.flush()

    for i, value in enumerate(spec["values"], start=1):
        cfg = spec["make_cfg"]()
        cfg.show_plot = False
        set_param(cfg, param, value)
        t0 = time.time()
        try:
            ensure_valid_start(cfg)
            prof = sb.analyse_chaos_phase_space(
                cfg, n_s=n_s, n_p=n_p, n_bounces=n_bounces, verbose=False)
        except ValueError as err:
            if verbose:
                print("{:>3}  {:>12}  SKIPPED: {}".format(i, value, err))
                sys.stdout.flush()
            continue

        lam = prof.lyap_exponent
        has_lam = lam == lam
        mfp = mean_free_path(cfg)
        rows.append({
            "N": i,
            "PARAM": value,
            "SALI_fraction": prof.chaotic_fraction,
            "regime": chaos_regime(prof.chaotic_fraction, prof.n_chaotic),
            "lambda": lam if has_lam else None,
            "lambda_err": prof.lyap_sem if has_lam else None,
            "L": prof.lyap_number if has_lam else None,
            "strength": chaos_strength(lam),
            "lambda_per_length": (lam / mfp) if (has_lam and mfp == mfp) else None,
            "mean_free_path": mfp,
            "KS_estimate": prof.ks_estimate,
            "n_chaotic": prof.n_chaotic,
            "n_regular": prof.n_regular,
            "n_failed": prof.n_failed,
            "grid_s": prof.n_s,
            "grid_p": prof.n_p,
            "bounces": prof.n_bounces,
            "wall_length": prof.perimeter,
            "seconds": round(time.time() - t0, 1),
        })

        if verbose:
            print("{:>3}  {:>12.5g}  {:>8.3f}  {:>9}  {:>8}  {:>8}  {}".format(
                i, value, prof.chaotic_fraction, rows[-1]["regime"],
                "{:.4f}".format(lam) if has_lam else "-",
                "{:.3f}".format(prof.lyap_number) if has_lam else "-",
                rows[-1]["strength"]))
            sys.stdout.flush()

    return Study(spec["key"], spec["title"], spec["board_note"],
                 param, label, rows, n_s, n_p, n_bounces)


# =============================================================================
# WRITING THE SPREADSHEET
# =============================================================================

def _slug(text):
    """Turn a typed tab title into a short, file-safe study key."""
    keep = [c if (c.isalnum() or c in " -_") else " " for c in text]
    return "_".join("".join(keep).split())[:31] or "sweep"


def _sheet_title(study):
    """Worksheet names cannot exceed 31 chars or contain []:*?/\\ ."""
    name = study.key
    for bad in "[]:*?/\\":
        name = name.replace(bad, "-")
    return name[:31]


def write_xlsx(studies, path):
    """
    Write one worksheet per study, plus a Legend page, as a real .xlsx.

    Google Sheets opens this directly and keeps the pages as separate tabs.
    Values go in as numbers (not strings) so charts and formulas work.

    An EXISTING file is merged into, not replaced: pages for studies not in
    this run are left untouched, and a page for a study that IS in this run is
    rebuilt from scratch. That way a workbook accumulates unrelated
    investigations across many sessions, and re-running one study refreshes
    only its own page.
    """
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    if os.path.exists(path):
        wb = load_workbook(path)
    else:
        wb = Workbook()
        wb.remove(wb.active)

    # Rebuild only the pages being written now (plus the Legend, always)
    for name in [_sheet_title(s) for s in studies] + ["Legend"]:
        if name in wb.sheetnames:
            wb.remove(wb[name])

    title_font = Font(bold=True, size=14)
    head_font = Font(bold=True)
    note_font = Font(italic=True, size=9, color="555555")
    head_fill = PatternFill("solid", fgColor="DDE6F0")

    for study in studies:
        ws = wb.create_sheet(_sheet_title(study))

        # --- the name on top ---
        ws.cell(row=1, column=1, value=study.title).font = title_font
        ws.cell(row=2, column=1, value="board: " + study.board_note).font = note_font
        ws.cell(row=3, column=1,
                value="varying: " + study.param_label).font = note_font
        ws.cell(row=4, column=1, value=(
            "chaos sampled uniformly over phase space "
            "({} x {} states, {} bounces each)"
            .format(study.n_s, study.n_p, study.n_bounces))).font = note_font
        ws.cell(row=5, column=1, value="generated " + datetime.datetime.now()
                .strftime("%Y-%m-%d %H:%M")).font = note_font

        # --- header ---
        head_row = 7
        for c, (name, width, _note) in enumerate(COLUMNS, start=1):
            text = study.param_label if name == "PARAM" else name
            cell = ws.cell(row=head_row, column=c, value=text)
            cell.font = head_font
            cell.fill = head_fill
            cell.alignment = Alignment(wrap_text=True, vertical="bottom")
            ws.column_dimensions[get_column_letter(c)].width = width

        # --- data ---
        for r, row in enumerate(study.rows, start=head_row + 1):
            for c, (name, _w, _note) in enumerate(COLUMNS, start=1):
                ws.cell(row=r, column=c, value=row.get(name))

        ws.freeze_panes = ws.cell(row=head_row + 1, column=3)

    # --- Legend page ---
    ws = wb.create_sheet("Legend")
    ws.cell(row=1, column=1, value="What every column means").font = title_font
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 100
    r = 3
    for name, _w, note in COLUMNS:
        ws.cell(row=r, column=1, value=name).font = head_font
        ws.cell(row=r, column=2, value=note).alignment = Alignment(wrap_text=True)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Bands for 'strength'").font = title_font
    r += 1
    ws.cell(row=r, column=1, value="lambda from").font = head_font
    ws.cell(row=r, column=2, value="label").font = head_font
    r += 1
    low = 0.0
    for hi, label in sb.LYAPUNOV_BANDS:
        ws.cell(row=r, column=1,
                value="{:.2f} - {}".format(low, "inf" if hi == float("inf")
                                           else "{:.2f}".format(hi)))
        ws.cell(row=r, column=2, value=label)
        low = hi
        r += 1

    r += 1
    ws.cell(row=r, column=1,
            value="Published per-collision anchors").font = title_font
    r += 1
    ws.cell(row=r, column=1, value="lambda").font = head_font
    ws.cell(row=r, column=2, value="system / source / buildable here?").font = head_font
    r += 1
    for lam, system, source, buildable in sb.LYAPUNOV_REFERENCE_TABLE:
        ws.cell(row=r, column=1, value=lam)
        ws.cell(row=r, column=2,
                value="{}  |  {}  |  {}".format(system, source, buildable))
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Health warnings").font = title_font
    r += 1
    for line in (
        "lambda is per COLLISION unless you use the lambda_per_length column.",
        "A regular orbit never reads exactly 0: it decays like log(n)/n, so "
        "short runs read slightly positive. Compare against the floor for "
        "your bounce count.",
        "'regular' means no chaos was FOUND, at this grid and this run length. "
        "A chaotic layer thinner than the grid spacing is invisible.",
        "The regular whispering-gallery region sits extremely close to grazing "
        "(|p| -> 1). A uniform p grid may step right over it.",
        "A SMALL scatterer needs MORE bounces, not fewer. With a tiny disk many "
        "orbits bounce off the walls for hundreds of collisions before ever "
        "reaching it, and until they do they look exactly like rectangle "
        "orbits. That is why the Sinai billiard - proven chaotic for ANY disk "
        "radius - can still be scored 'mixed' at small radii on a short run.",
    ):
        ws.cell(row=r, column=2, value=line).alignment = Alignment(wrap_text=True)
        r += 1

    wb.save(path)
    return path


def write_tsv(study, path):
    """
    Same page as a tab-separated file, for pasting straight into Sheets.

    Kept as a fallback for when openpyxl is unavailable, and because pasting
    is sometimes faster than importing a file.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(study.title + "\n")
        f.write("board: " + study.board_note + "\n")
        f.write("varying: " + study.param_label + "\n")
        f.write("grid: {} x {} states, {} bounces\n\n".format(
            study.n_s, study.n_p, study.n_bounces))
        f.write("\t".join(study.param_label if n == "PARAM" else n
                          for n, _w, _note in COLUMNS) + "\n")
        for row in study.rows:
            out = []
            for name, _w, _note in COLUMNS:
                v = row.get(name)
                out.append("" if v is None else
                           ("{:.6g}".format(v) if isinstance(v, float) else str(v)))
            f.write("\t".join(out) + "\n")
    return path


# =============================================================================
# THE STUDIES
# =============================================================================

def _circle():
    c = sb.Config()
    c.board_shape = "polar"
    c.polar_r0 = 1.0
    c.polar_a1 = c.polar_b1 = 0.0
    c.polar_a2 = c.polar_b2 = c.polar_a3 = c.polar_b3 = 0.0
    c.obstacle_shape = "none"
    c.start_x, c.start_y = 0.25, 0.15
    return c


def _ellipse(ratio=2.0):
    c = sb.Config()
    c.board_shape = "ellipse"
    c.board_size = 1.0
    c.board_ratio = ratio
    c.ellipse_bump = 0.0
    c.ellipse_bump_n = 2
    c.obstacle_shape = "none"
    c.start_x, c.start_y = 0.2, 0.15
    return c


def _stadium():
    c = sb.Config()
    c.board_shape = "stadium"
    c.board_size = 1.0
    c.stadium_half_length = 1.0
    c.stadium_curve = 1.0
    c.obstacle_shape = "none"
    c.start_x, c.start_y = 0.15, 0.25
    return c


def _sinai():
    c = sb.Config()
    c.board_shape = "rectangle"
    c.board_size = 1.0
    c.board_ratio = 1.0
    c.obstacle_shape = "circle"
    c.obstacle_x = c.obstacle_y = 0.0
    c.obstacle_rx = c.obstacle_ry = 0.3
    c.start_x, c.start_y = 0.6, 0.6
    return c


# Sweep values are deliberately DENSE NEAR ZERO. The onset of chaos is not
# linear in the deformation: a uniform grid spends most of its points in the
# boring saturated region and steps straight over the transition.
FINE_ONSET = [0.0, 0.01, 0.02, 0.05, 0.08, 0.12, 0.2, 0.3, 0.5, 0.7, 1.0]

STUDIES = [
    {
        "key": "circle_sin1",
        "title": "Circle deformed by a*sin(theta)",
        "board_note": "polar r(theta) = 1 + a sin(theta); a = 0 is the unit circle",
        "make_cfg": _circle,
        "param": "polar_b1",
        "values": FINE_ONSET,
    },
    {
        "key": "circle_cos1_limacon",
        "title": "Circle deformed by a*cos(theta) (Robnik limacon)",
        "board_note": ("polar r(theta) = 1 + a cos(theta); a = 0 circle, "
                       "a = 0.5 curvature first vanishes, a = 1 cardioid"),
        "make_cfg": _circle,
        "param": "polar_a1",
        "values": FINE_ONSET,
    },
    {
        "key": "circle_cos2",
        "title": "Circle deformed by a*cos(2 theta)",
        "board_note": "polar r(theta) = 1 + a cos(2 theta); a = 0 is the unit circle",
        "make_cfg": _circle,
        "param": "polar_a2",
        "values": [0.0, 0.01, 0.02, 0.05, 0.08, 0.12, 0.2, 0.3],
    },
    {
        "key": "ellipse_dent",
        "title": "Ellipse (rx/ry = 2) with a growing dent",
        "board_note": ("r = r_ellipse(theta) * (1 + eps cos 2theta); "
                       "eps = 0 is the exact integrable ellipse"),
        "make_cfg": _ellipse,
        "param": "ellipse_bump",
        "values": [0.0, 0.005, 0.01, 0.02, 0.05, 0.08, 0.12, 0.2, 0.3],
    },
    {
        "key": "stadium_gamma",
        "title": "Stadium: straight section growing from zero",
        "board_note": ("semicircular caps (c = 1), half-height r = 1, "
                       "a = 0 is a circle; gamma = a/r"),
        "make_cfg": _stadium,
        "param": "stadium_half_length",
        "values": [0.0, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0],
    },
    {
        "key": "stadium_curve",
        "title": "Stadium at gamma = 1: level of curving",
        "board_note": ("a = r = 1; c = 1 gives semicircular caps (classic "
                       "Bunimovich stadium), smaller c gives shallower caps"),
        "make_cfg": _stadium,
        "param": "stadium_curve",
        "values": [0.05, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0],
    },
    {
        "key": "sinai_disk",
        "title": "Sinai billiard: unit square with a centred disk",
        "board_note": "square of half-side 1, central disk of varying radius",
        "make_cfg": _sinai,
        "param": "obstacle_r",
        "values": [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6],
    },
]

STUDY_BY_KEY = {s["key"]: s for s in STUDIES}


def sweepable_params(cfg):
    """
    Which parameters make sense to sweep on the board cfg currently describes.

    Offering `stadium_curve` on a circle would just produce a column of
    identical rows, so the list is filtered by shape.
    """
    shape = cfg.board_shape
    if shape == "stadium":
        names = ["stadium_curve", "stadium_half_length", "board_size"]
    elif shape == "ellipse":
        names = ["ellipse_bump", "ellipse_bump_n", "board_ratio", "board_size"]
    elif shape == "polar":
        names = ["polar_a1", "polar_b1", "polar_a2", "polar_b2",
                 "polar_a3", "polar_b3", "polar_r0"]
    elif shape == "circle":
        names = ["board_size"]
    else:  # rectangle
        names = ["board_ratio", "board_size"]
    if cfg.obstacle_shape != "none":
        names.append("obstacle_r")
    return names


def ask_values(prompt):
    """Read a list of numbers typed as '0, 0.05, 0.1' or as a from:to:step range."""
    while True:
        raw = input(prompt + ": ").strip()
        if not raw:
            print("  Type at least one number.")
            continue
        try:
            if ":" in raw:
                parts = [float(p) for p in raw.split(":")]
                if len(parts) != 3 or parts[2] <= 0:
                    raise ValueError
                start, stop, step = parts
                values, v = [], start
                # Half a step of slack so the endpoint survives rounding
                while v <= stop + step * 0.5:
                    values.append(round(v, 10))
                    v += step
            else:
                values = [float(p) for p in raw.replace(",", " ").split()]
        except ValueError:
            print("  Could not read that. Use '0, 0.05, 0.1' or 'from:to:step'.")
            continue
        if values:
            return values


def interactive_sweep(cfg, out="chaos_studies.xlsx"):
    """
    Sweep one parameter of the board the user has already set up, and append
    the results to the spreadsheet as a new tab.

    This is the menu-driven twin of `main`: same measurement, same columns,
    same workbook, but the board comes from the live config instead of one of
    the STUDIES presets.
    """
    print("\n--- EXPORT A SWEEP TO A SPREADSHEET ---")
    print("Takes the board you have set up, changes ONE number over a range,")
    print("measures the chaos at each value, and writes a tab you can open")
    print("in Google Sheets.")

    names = sweepable_params(cfg)
    print("\nParameters you can sweep on this {} board:".format(cfg.board_shape))
    for i, name in enumerate(names, start=1):
        print("  {}  {:<22} {}".format(
            i, name, PARAM_LABELS.get(name, "")))
    print("  p  use a preset study instead (ignores the board above)")

    pick = input("\nChoose [1-{}/p]: ".format(len(names))).strip().lower()
    if pick == "p":
        for s in STUDIES:
            print("  {:<22} {}".format(s["key"], s["title"]))
        key = input("Preset key: ").strip()
        if key not in STUDY_BY_KEY:
            print("Unknown preset. Nothing done.")
            return
        spec = STUDY_BY_KEY[key]
    else:
        try:
            param = names[int(pick) - 1]
        except (ValueError, IndexError):
            print("Not a listed choice. Nothing done.")
            return
        current = getattr(cfg, param, None) if param != "obstacle_r" \
            else cfg.obstacle_rx
        print("\nSweeping {}. Current value: {}".format(param, current))
        print("Type the values as a list '0, 0.05, 0.1' or a range "
              "'from:to:step'.")
        values = ask_values("Values")
        title = input("Tab title (Enter = auto): ").strip()
        title = title or "{} board: varying {}".format(cfg.board_shape, param)
        base = copy.deepcopy(cfg)
        spec = {
            # The tab is named after the title, not the parameter, so two
            # sweeps of the same parameter on different boards land on
            # different pages instead of overwriting each other.
            "key": _slug(title),
            "title": title,
            "board_note": sb.describe_board(base),
            "make_cfg": lambda: copy.deepcopy(base),
            "param": param,
            "values": values,
        }

    print("\nHow careful should the measurement be?")
    print("  1  quick  10 x 7 states, 200 bounces   (first look)")
    print("  2  normal 14 x 11 states, 300 bounces")
    print("  3  fine   24 x 15 states, 500 bounces  (final numbers, slow)")
    level = input("Choose [1/2/3, Enter = 2]: ").strip()
    n_s, n_p, nb = {"1": (10, 7, 200), "3": (24, 15, 500)}.get(
        level, (14, 11, 300))

    n_orbits = len(spec["values"]) * n_s * n_p
    print("\nThat is {} values x {} states = {} orbits.".format(
        len(spec["values"]), n_s * n_p, n_orbits))
    if input("Run it? [y/N]: ").strip().lower() not in ("y", "yes"):
        print("Cancelled.")
        return

    t0 = time.time()
    study = run_study(spec, n_s=n_s, n_p=n_p, n_bounces=nb)
    try:
        write_xlsx([study], out)
        print("\nDone in {:.0f} s. Added the tab '{}' to {}".format(
            time.time() - t0, _sheet_title(study), out))
        print("Upload that file to Google Drive and open it - each sweep is a tab.")
    except ImportError:
        path = study.key + ".tsv"
        write_tsv(study, path)
        print("\n(openpyxl missing, so wrote {} instead - paste it into Sheets.)"
              .format(path))


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}

    if not args or "--help" in flags or "-h" in flags:
        print(__doc__)
        print("Studies available:\n")
        for s in STUDIES:
            print("  {:<22} {}".format(s["key"], s["title"]))
        print("\n  all                    run every study above")
        print("\nFlags:")
        print("  --quick      coarse grid, fast, for a first look")
        print("  --fine       dense grid, slow, for final numbers")
        print("  --tsv        also write one .tsv per page for pasting")
        print("  --out=NAME   output file name (default chaos_studies.xlsx)")
        return 0

    if "--quick" in flags:
        n_s, n_p, nb = 10, 7, 200
    elif "--fine" in flags:
        n_s, n_p, nb = 24, 15, 500
    else:
        n_s, n_p, nb = 14, 11, 300

    out = "chaos_studies.xlsx"
    for f in flags:
        if f.startswith("--out="):
            out = f.split("=", 1)[1]

    keys = list(STUDY_BY_KEY) if "all" in args else args
    unknown = [k for k in keys if k not in STUDY_BY_KEY]
    if unknown:
        print("Unknown study: {}".format(", ".join(unknown)))
        print("Known: {}".format(", ".join(STUDY_BY_KEY)))
        return 1

    total_orbits = sum(len(STUDY_BY_KEY[k]["values"]) for k in keys) * n_s * n_p
    print("Running {} study page(s), about {} orbits in total."
          .format(len(keys), total_orbits))
    print("Polar and dented boards have no closed-form wall, so they are the "
          "slow ones.")

    t0 = time.time()
    studies = []
    for k in keys:
        studies.append(run_study(STUDY_BY_KEY[k], n_s=n_s, n_p=n_p,
                                 n_bounces=nb))
        # Save after every page, so a long run is never lost to a crash
        try:
            write_xlsx(studies, out)
        except ImportError:
            print("  (openpyxl missing - writing .tsv pages instead)")
            for st in studies:
                write_tsv(st, st.key + ".tsv")

    if "--tsv" in flags:
        for st in studies:
            write_tsv(st, st.key + ".tsv")

    print("\nDone in {:.0f} s.".format(time.time() - t0))
    if os.path.exists(out):
        print("Wrote {} ({} pages + Legend)".format(out, len(studies)))
        print("\nTo get it into Google Sheets:")
        print("  upload it to Google Drive and open it - each study is a tab,")
        print("  or in Sheets use File > Import and pick 'Insert new sheet(s)'.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
