"""
Generate a PDF listing the exact papers whose published Lyapunov / KS-entropy
values disagree, their parameters, and what this simulator measures.

Run:  py make_lyapunov_report.py
Output: lyapunov_literature_report.pdf
"""

import math
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = "lyapunov_literature_report.pdf"

ZETA3 = 1.2020569031595942854
ZETA2 = math.pi * math.pi / 6.0

C_DAHLQVIST = 1.0 - 4.0 * math.log(2.0) + 27.0 * ZETA3 / (2.0 * math.pi ** 2)
C_BOCA = 2.0 - 3.0 * math.log(2.0) + 9.0 * ZETA3 / (4.0 * ZETA2)
GAP = 1.0 + math.log(2.0)

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15, spaceAfter=4,
                    textColor=colors.HexColor("#111111"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11.5,
                    spaceBefore=11, spaceAfter=4,
                    textColor=colors.HexColor("#1a3a6b"))
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontSize=9.4,
                      leading=13.2, alignment=TA_LEFT, spaceAfter=5)
MONO = ParagraphStyle("MONO", parent=BODY, fontName="Courier", fontSize=8.6,
                      leading=11.6, leftIndent=8, spaceAfter=5)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.2, leading=11,
                       textColor=colors.HexColor("#444444"))
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.3, leading=10.8,
                      spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")


def table(data, widths, align_right=()):
    rows = []
    for r_i, row in enumerate(data):
        cells = []
        for c_i, txt in enumerate(row):
            st = CELLB if r_i == 0 else CELL
            cells.append(Paragraph(str(txt), st))
        rows.append(cells)
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf5")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#1a3a6b")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d2e0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for r_i in range(1, len(data)):
        if r_i % 2 == 0:
            style.append(("BACKGROUND", (0, r_i), (-1, r_i),
                          colors.HexColor("#f7f9fc")))
    t.setStyle(TableStyle(style))
    return t


def build():
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=18 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Published Lyapunov values for billiards: sources, parameters "
              "and a contradiction",
        author="sinai_billiards benchmark",
    )
    S = []
    W = doc.width

    S.append(Paragraph(
        "Published Lyapunov values for billiards:<br/>sources, parameters, "
        "and one outright contradiction", H1))
    S.append(Paragraph(
        "Reference material for the Lyapunov-number checker in "
        "<font face='Courier'>sinai_billiard.py</font>. "
        "Every value below is per <b>collision</b> (billiard map), not per "
        "unit time, unless stated otherwise. Measurements come from "
        "<font face='Courier'>bench_lyapunov.py</font>.", SMALL))

    # ---------------------------------------------------------------- part 1
    S.append(Paragraph("1. The contradiction: two papers, same quantity, "
                       "different constant", H2))
    S.append(Paragraph(
        "Both papers describe the Kolmogorov&ndash;Sinai entropy / Lyapunov "
        "exponent of the <b>same</b> map: the disk-to-disk billiard map of a "
        "circular scatterer of radius R centred in a unit square (equivalently "
        "the periodic 2D Lorentz gas on the unit lattice). For a 2D map with a "
        "single positive exponent, Pesin's identity forces h&nbsp;=&nbsp;&lambda;, "
        "so the two formulas must agree. They do not.", BODY))

    S.append(table([
        ["", "Paper A &mdash; Dahlqvist (1997)",
         "Paper B &mdash; Boca &amp; Zaharescu (2007)"],
        ["Title",
         "The Lyapunov exponent in the Sinai billiard in the small scatterer "
         "limit",
         "The distribution of the free path lengths in the periodic "
         "two-dimensional Lorentz gas in the small-scatterer limit"],
        ["Author(s)", "Per Dahlqvist (KTH, Stockholm)",
         "Florin P. Boca, Alexandru Zaharescu (Univ. of Illinois "
         "Urbana&ndash;Champaign)"],
        ["Venue", "Nonlinearity <b>10</b> (1997), article 011",
         "Commun. Math. Phys. <b>269</b> (2007), no. 2, 425&ndash;471 "
         "(arXiv preprint 2003)"],
        ["DOI / arXiv",
         "doi:10.1088/0951-7715/10/1/011<br/>arXiv:chao-dyn/9601007",
         "doi:10.1007/s00220-006-0137-7<br/>arXiv:math/0301270"],
        ["Where in the paper", "eqs. (74) and (75); see also eq. (31), (73)",
         "Abstract, and Theorem 3(ii); discussion before Theorem 3"],
        ["Stated result",
         "&lambda; = &minus;2&nbsp;log&nbsp;R + C + O(R&nbsp;log<super>2</super>R)"
         "<br/>C = 1 &minus; 4&nbsp;log&nbsp;2 + 27&zeta;(3)/(2&pi;<super>2</super>)",
         "h(T<sub>&epsilon;</sub>) = &minus;2&nbsp;ln&nbsp;&epsilon; + 2 "
         "&minus; 3&nbsp;ln&nbsp;2 + 9&zeta;(3)/(4&zeta;(2)) + o(1)"],
        ["Constant, evaluated",
         "<b>%+.8f</b>" % C_DAHLQVIST,
         "<b>%+.8f</b>" % C_BOCA],
    ], [0.16 * W, 0.42 * W, 0.42 * W]))

    S.append(Spacer(1, 5))
    S.append(Paragraph(
        "The two constants differ by exactly "
        "1&nbsp;+&nbsp;log&nbsp;2&nbsp;=&nbsp;%.6f. Note that "
        "27&zeta;(3)/(2&pi;<super>2</super>) and 9&zeta;(3)/(4&zeta;(2)) are "
        "the same number (%.8f), so the &zeta;(3) part is not the problem: the "
        "disagreement is entirely in the prefactor, "
        "<b>2</b> versus <b>1&nbsp;&minus;&nbsp;log&nbsp;2</b>." % (
            GAP, 27.0 * ZETA3 / (2.0 * math.pi ** 2)), BODY))

    S.append(Paragraph("Where the discrepancy enters", H2))
    S.append(Paragraph(
        "Dahlqvist's own intermediate result, his eq. (31), is", BODY))
    S.append(Paragraph(
        "&lambda; = &minus;2 log R &minus; log 2 + 1 + c(R) + O(R),"
        "&nbsp;&nbsp; with c(R) = 27&zeta;(3)/(2&pi;<super>2</super>) "
        "&minus; 3 log 2&nbsp;&nbsp;[his eq. (73)]", MONO))
    S.append(Paragraph(
        "Boca &amp; Zaharescu quote that same c(R) &mdash; they write "
        "&ldquo;the constant C was identified by Dahlqvist [14, formula (73)] "
        "as being 3&nbsp;ln&nbsp;2&nbsp;&minus;&nbsp;9&zeta;(3)/(4&zeta;(2)) = "
        "0.43522513609&hellip;&rdquo; &mdash; but insert it into a different "
        "envelope, h = &minus;2&nbsp;ln&nbsp;&epsilon;&nbsp;+&nbsp;2&nbsp;"
        "&minus;&nbsp;C, which they attribute to Friedman&ndash;Kubo&ndash;Oono "
        "and to Chernov's relation (2.8), not to Dahlqvist. So Dahlqvist's "
        "&ldquo;&minus;log&nbsp;2&nbsp;+&nbsp;1&rdquo; = %.5f is replaced by "
        "&ldquo;2&rdquo;, which is precisely the %.4f gap." % (
            1 - math.log(2), GAP), BODY))

    S.append(Paragraph("What this simulator measures", H2))
    S.append(Paragraph(
        "A square box with reflecting walls and a centred disk unfolds by "
        "mirror reflection into exactly the unit-lattice Lorentz gas, so the "
        "scaled radius is R = disk_radius / box_side. Published values are per "
        "<i>disk</i> collision, so each orbit was rescaled by "
        "n<sub>total</sub>/n<sub>disk</sub> (flat walls contribute no "
        "stretching). Least-squares fit over R = 0.10&hellip;0.40, "
        "3000 collisions per orbit, 60 orbits per radius:", BODY))
    S.append(table([
        ["Quantity", "Measured", "Paper A", "Paper B"],
        ["slope in log R", "<b>&minus;2.0584</b>",
         "&minus;2 (exact)", "&minus;2 (exact)"],
        ["constant", "<b>&minus;0.1256</b>",
         "%+.5f" % C_DAHLQVIST, "%+.5f" % C_BOCA],
        ["agreement", "&mdash;", "within 2%", "off by 1.69"],
    ], [0.25 * W, 0.25 * W, 0.25 * W, 0.25 * W]))
    S.append(Spacer(1, 4))
    S.append(Paragraph(
        "<b>Conclusion: the measurement supports Paper A.</b> Paper B's "
        "constant is not merely imprecise, it is displaced by 1&nbsp;+&nbsp;"
        "log&nbsp;2. Caveat: Dahlqvist's law is asymptotic as R&nbsp;&rarr;&nbsp;0 "
        "with error O(R&nbsp;log<super>2</super>R), which is still of order 0.5 "
        "across the R range reachable here, so the <i>slope</i> is the sharp "
        "test and the constant is indicative &mdash; but a 1.69 displacement is "
        "far outside that uncertainty.", BODY))

    # ---------------------------------------------------------------- part 2
    S.append(Paragraph("2. A milder disagreement: the cardioid billiard", H2))
    S.append(Paragraph(
        "Board r(&theta;) = 1 + cos&nbsp;&theta;, no obstacle "
        "(<font face='Courier'>polar_r0=1, polar_a1=1</font> in this "
        "simulator). Two independent papers give per-collision values that "
        "differ from each other by 1.8%.", BODY))
    S.append(table([
        ["Source", "Reference", "Parameters", "Value",
         "Measured here"],
        ["B&auml;cker &amp; Dullin (1997), eq. (59)",
         "J. Phys. A <b>30</b> (1997) 1991;<br/>"
         "doi:10.1088/0305-4470/30/6/023",
         "r = 1 + cos&nbsp;&theta;; h<sub>KS</sub> from the linearised map, "
         "5&times;10<super>6</super> iterations",
         "h<sub>KS</sub> = 0.653", "0.6464 (&minus;1.0%)"],
        ["Same paper, eq. (58) &mdash; geometry cross-check",
         "as above",
         "mean length between reflections, "
         "&lang;l&rang; = 3&pi;<super>2</super>/16",
         "&lang;l&rang; = 1.851", "1.8379 (&minus;0.7%)"],
        ["Same paper, sec. 5 &mdash; analytic bound",
         "as above (Wojtkowski's theorem)",
         "numerical integration of the lower-bound integral",
         "h<sub>KS</sub> &ge; 0.633", "consistent"],
        ["Out-of-time-order correlators (2024), Table 1",
         "arXiv:2408.04052",
         "r(&gamma;) = 1 + &epsilon;&nbsp;cos&nbsp;&gamma; with &epsilon; = 1; "
         "trajectory-pair separation vs collision index",
         "&lambda;<sub>cl</sub> = 0.6649", "0.6464 (&minus;2.8%)"],
    ], [0.22 * W, 0.21 * W, 0.25 * W, 0.16 * W, 0.16 * W]))
    S.append(Spacer(1, 4))
    S.append(Paragraph(
        "0.653 and 0.6649 cannot both be the same limit, so at least one of "
        "the two papers is off by more than its own precision. Our 0.6464 "
        "sits just below both. Because the measured &lang;l&rang; is also "
        "0.7% low, part of our own shortfall is boundary geometry (the "
        "cardioid cusp at the origin) rather than the Lyapunov algorithm.",
        BODY))

    # ---------------------------------------------------------------- part 3
    S.append(Paragraph("3. Exactly known values used as ground truth", H2))
    S.append(Paragraph(
        "These are not disputed and serve to validate the checker itself.",
        BODY))
    S.append(table([
        ["Case", "Source", "Exact value", "Measured"],
        ["Two-disk / disk-plus-flat-wall fundamental periodic orbit; "
         "disk radius a, centre separation R",
         "P. Cvitanovic et al., <i>ChaosBook</i> "
         "(chaosbook.org), 3-disk fundamental cycle",
         "&Lambda; = R/a &minus; 1 + (R/a)&radic;(1&minus;2a/R),"
         "<br/>&lambda; = log&nbsp;&Lambda;&nbsp;/&nbsp;2",
         "agrees to 1&times;10<super>&minus;9</super> relative "
         "(5 geometries)"],
        ["Circle, ellipse, rectangle (integrable)",
         "classical; no chaos, KAM tori",
         "&lambda; = 0 exactly",
         "&rarr; 0 like log&nbsp;n&nbsp;/&nbsp;n, as required"],
    ], [0.26 * W, 0.24 * W, 0.26 * W, 0.24 * W]))

    # ---------------------------------------------------------------- part 4
    S.append(Paragraph("4. Values quoted but not testable here", H2))
    S.append(table([
        ["Case", "Source", "Value", "Why not tested"],
        ["Bunimovich stadium, maximum over shape parameter "
         "&gamma; = a/r",
         "G. Benettin &amp; J.-M. Strelcyn, Phys. Rev. A <b>17</b> (1978) "
         "773&ndash;785; reproduced in Sci. Rep. <b>12</b> (2022) 4787 "
         "(doi:10.1038/s41598-022-08897-4)",
         "&lambda; &asymp; 0.43 at &gamma; = 1; &lambda; = 0 at &gamma; = 0",
         "This simulator has no stadium boundary "
         "(rectangle / circle / ellipse / polar only), and a polar "
         "r(&theta;) cannot reproduce one."],
        ["&ldquo;Sinai&rdquo; billiard of the OTOC paper",
         "arXiv:2408.04052, Table 1",
         "&lambda;<sub>cl</sub> = 0.8048, d<sub>avg</sub> = 0.4817 at area 1",
         "Box-to-disk geometry is not specified precisely enough to "
         "rebuild."],
        ["Small-scatterer universality "
         "lim h&lang;&tau;&rang;/(&minus;ln&nbsp;&epsilon;) = d",
         "B. Friedman, Y. Oono, I. Kubo, Phys. Rev. Lett. <b>52</b> (1984) 709",
         "= d (space dimension); C estimated 0.44 &plusmn; 0.001",
         "A scaling statement about the &epsilon;&nbsp;&rarr;&nbsp;0 limit "
         "rather than a value at fixed R; its numeric estimate of C is "
         "superseded by Dahlqvist's closed form."],
        ["Sinai's entropy formula for hyperbolic billiards",
         "N. I. Chernov, Funct. Anal. Appl. <b>25</b> (1991) 204&ndash;219 "
         "(doi:10.1007/BF01085490)",
         "proves boundedness of C<sub>&epsilon;</sub>, no numeric bound",
         "Provides the h&nbsp;&harr;&nbsp;&lang;&tau;&rang; relation that "
         "Paper B relies on; no standalone number to test."],
    ], [0.24 * W, 0.28 * W, 0.24 * W, 0.24 * W]))

    # ---------------------------------------------------------------- part 5
    S.append(Paragraph("5. Conventions that must match before comparing", H2))
    S.append(Paragraph(
        "Most apparent disagreements in this literature are convention "
        "mismatches, not physics:", BODY))
    S.append(table([
        ["Convention", "Effect if mixed up"],
        ["per collision (map) vs per unit time/length (flow)",
         "differ by the mean free path &lang;l&rang;; for the cardioid that is "
         "a factor 1.85 (0.653 per collision = 0.36 per unit length)"],
        ["all collisions vs scatterer collisions only",
         "at R = 0.10 only 13.6% of collisions hit the disk, so the raw "
         "per-collision average reads 0.62 against a true 4.58 &mdash; a "
         "factor of 7"],
        ["Lyapunov number L vs exponent &lambda;",
         "L = e<super>&lambda;</super>; L = 2 and &lambda; = 2 are very "
         "different boards"],
        ["scatterer radius R normalised to the lattice / box side",
         "shifts the constant by &minus;2&nbsp;log(scale); using the box "
         "half-size instead of the side moves it by 2&nbsp;log&nbsp;2 = 1.386"],
    ], [0.32 * W, 0.68 * W]))

    S.append(Spacer(1, 8))
    S.append(Paragraph(
        "Generated by <font face='Courier'>make_lyapunov_report.py</font> in "
        "the sinai_billiards project. Measurements reproducible with "
        "<font face='Courier'>py bench_lyapunov.py</font>.", SMALL))

    doc.build(S)
    print("wrote " + os.path.abspath(OUT))


if __name__ == "__main__":
    build()
