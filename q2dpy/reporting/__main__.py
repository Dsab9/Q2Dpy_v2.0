"""Command line entry point for building a calibration report from a finished run.

Run it from the q2dpy folder (the folder that contains this package):

    python -m reporting <output folder> [--tol 0.03] [--input-dir DIR] [--config NAME] [--report-root DIR]
"""
import argparse

from .builder import make_report


def main():
    ap = argparse.ArgumentParser(
        prog=f"python -m {__package__}",
        description="Build a calibration report for a finished Q2Dpy run.")
    ap.add_argument("output_dir", help="the run's Output/<run name> folder")
    ap.add_argument("--input-dir", help="snapshot folder (default: sibling Input/<run name>)")
    ap.add_argument("--config", help="TOML name inside the snapshot folder, if there are several")
    ap.add_argument("--report-root", help="folder that receives report folders (default: <project>/reporting)")
    ap.add_argument("--tol", type=float, help="acceptance tolerance in meters (overrides the config value)")
    args = ap.parse_args()

    try:
        report = make_report(args.output_dir, args.input_dir, args.config, args.report_root, args.tol)
        report.run()
    except (FileNotFoundError, ValueError, NotImplementedError) as exc:
        raise SystemExit(f"Report not created: {exc}")


if __name__ == "__main__":
    main()