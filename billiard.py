"""
Mathematical billiards - one entry point for everything in this project.

    py billiard.py                  the interactive menu (set up a board,
                                    watch paths, measure chaos, export)
    py billiard.py study <name>     run a preset parameter sweep and write
                                    the spreadsheet, without the menu
    py billiard.py bench            check the chaos numbers against the
                                    published literature values
    py billiard.py report           build the PDF on the literature
                                    disagreements

Run any subcommand with --help for its own options, e.g.

    py billiard.py study --help

The physics all lives in sinai_billiard.py, which stays importable as a plain
library; this file only decides which front end to start. Each subcommand
imports its own module lazily, so a missing optional package (openpyxl for
spreadsheets, reportlab for the PDF) only breaks that one subcommand instead
of stopping the program from starting.
"""

import sys

USAGE = __doc__


def main(argv):
    if argv and argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    # No subcommand: the menu is what most sessions want.
    command = argv[0] if argv else "menu"
    rest = argv[1:]

    if command == "menu":
        import sinai_billiard
        sinai_billiard.main()
        return 0

    if command == "study":
        import chaos_studies
        # No study named: show the list rather than doing nothing.
        return chaos_studies.main(rest or ["--help"])

    if command == "bench":
        import bench_lyapunov
        bench_lyapunov.main()
        return 0

    if command == "report":
        try:
            import make_lyapunov_report
        except ImportError:
            print("The PDF report needs the reportlab package:")
            print("    pip install reportlab")
            return 1
        make_lyapunov_report.build()
        return 0

    print("Unknown command '{}'.\n".format(command))
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
