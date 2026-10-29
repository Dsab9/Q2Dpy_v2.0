r"""Calibration reports for Q2Dpy: PNG figures, CSV tables and one self-contained HTML page.

Works from a finished run's folders only (Output/<run> plus the Input/<run> snapshot that holds
the config TOML), so it can run at the end of main or later on any existing dataset:

    from reporting import make_report
    make_report(r"C:\...\Output\20261029_cal_observed").run()

    python reporting.py C:\...\Output\20261029_cal_observed --tol 0.03
"""
import argparse
import base64
import html
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import data as rd
import plots as rp
from ..units import cms_to_cfs

DEFAULT_REPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "reporting"

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;max-width:1000px;margin:2em auto;padding:0 1em;color:#222}
h1{border-bottom:2px solid #345;padding-bottom:.2em} h2{margin-top:1.6em;border-bottom:1px solid #ccc}
table.tbl{border-collapse:collapse;margin:.6em 0;font-size:.9em}
table.tbl th,table.tbl td{border:1px solid #ccc;padding:.25em .7em;text-align:right}
table.tbl th{background:#eef2f6} img{max-width:100%;margin:.5em 0}
.flag{background:#fff4e0;border-left:4px solid #e69500;padding:.4em .8em;margin:.4em 0}
.note{color:#555;font-size:.9em} .ok{background:#eaf6ea;border-left:4px solid #3a9a3a;padding:.4em .8em}
"""


class CalibrationReport:
    """Report on one finished calibration run. Subclasses add mode-specific sections."""

    mode_title = "Calibration"

    def __init__(self, output_dir, input_dir=None, config_name=None, report_root=None, tol_m=None):
        self.output_dir, self.input_dir = rd.resolve_run_folders(output_dir, input_dir)
        if not self.output_dir.is_dir():
            raise FileNotFoundError(f"Output folder not found: {self.output_dir}")
        self.toml_path = rd.find_snapshot_toml(self.input_dir, config_name)
        self.raw, self.s = rd.load_settings(self.toml_path)
        if self.s.get("batch_process"):
            raise NotImplementedError("Reports for batch calibrations are not implemented yet.")

        self.run_name = self.output_dir.name
        self.project = self.raw.get("ras", {}).get("prj", "project")
        self.tol_arg = tol_m
        self.report_root = Path(report_root) if report_root else DEFAULT_REPORT_ROOT
        self.report_dir = None
        self.figures = []          # (title, caption, path)
        self.tables = {}           # name -> DataFrame
        self.flags = []
        self.notes = []

    # ----------------------------------------------------------------- loading
    def load(self):
        """Reads the run's result files."""
        outs = self.raw["outputs"]
        self.iterations = rd.load_iterations(self.output_dir / outs["iterations_filename"])
        self.profiles = rd.load_profiles(self.output_dir / outs["wse_prof_filename"])
        self.plan_meta = rd.read_plan_metadata(self.raw)
        self.objective_name = self.s.get("objective_function", "RMSE")
        return self

    # ---------------------------------------------------------------- analysis
    def analyze(self):
        """Best run, parameters, acceptable runs, residual statistics and flags."""
        df = self.iterations
        self.params, self.bounds_map = rd.calibrated_parameters(self.s, df)
        if not self.params:
            raise ValueError("No calibrated parameter columns found in the iterations file.")

        self.best = rd.best_run(df)
        self.best_obj = float(self.best["Obj_Func_Value"])
        self.tol, self.tol_source = rd.resolve_tolerance(self.tol_arg, self.s, self.best_obj)
        self.acc = rd.acceptable_runs(df, self.best_obj, self.tol)
        self.ranges = rd.parameter_ranges(self.acc, self.best, self.params, self.bounds_map)
        self.stop = rd.stop_summary(df, self.s)

        self.flags += rd.bound_flags(self.best, self.params, self.bounds_map)
        if len(self.acc) < 5:
            self.flags.append(f"Only {len(self.acc)} run(s) fall within the tolerance, so the acceptable ranges "
                              "are a lower bound on the true spread.")

        self.residuals = rd.residual_table(self.profiles, self.best["iteration"])
        self.fit = rd.fit_statistics(self.residuals["Residual"]) if self.residuals is not None else {}
        if self.residuals is None:
            self.notes.append("Residual analysis skipped: WSE profile file or the best iteration's column is missing.")
        else:
            self.tables["worst_points"] = rd.worst_points(self.residuals)
            self.tables["residuals"] = self.residuals
        self.tables["parameter_ranges"] = self.ranges
        self.tables["acceptable_runs"] = self.acc
        self.tables["best_runs"] = df.nsmallest(10, "Obj_Func_Value")
        return self

    # ---------------------------------------------------------------- plotting
    def plot(self):
        """Saves the figures into <report folder>/figures."""
        fig_dir = self.report_dir / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        df = self.iterations

        self.figures.append(("Convergence",
                             "Objective for every model run, with the running best. The lower panel is the standard "
                             "deviation of the last two simplexes' objective values; early stopping ends the run when "
                             "it falls below the dashed line.",
                             rp.plot_convergence(df, self.objective_name, self.s.get("early_stop_tol"),
                                                 fig_dir / "convergence.png")))
        self.figures.append(("Parameters vs iteration",
                             "How each calibrated parameter moved. The star is the best run; dashed lines are the bounds.",
                             rp.plot_parameters_vs_iteration(df, self.params, self.bounds_map,
                                                             fig_dir / "parameters_vs_iteration.png")))
        self.figures.append(("Objective vs parameter",
                             "A narrow dip means the parameter is well constrained by the data; a flat floor means "
                             "many values fit about equally well.",
                             rp.plot_objective_vs_parameter(df, self.params, self.objective_name, self.best,
                                                            self.tol, fig_dir / "objective_vs_parameter.png")))
        if self.profiles is not None and f"I{int(self.best['iteration'])}" in self.profiles.columns:
            self.figures.append(("Water surface profile",
                                 "Measured points against the best modeled profile; grey lines are the other iterations.",
                                 rp.plot_profile(self.profiles, self.best["iteration"], fig_dir / "profile.png")))
        if self.residuals is not None:
            self.figures.append(("Residuals",
                                 "A trend along the reach points to a slope or roughness problem; one large outlier "
                                 "points to a questionable mark. The green band is the tolerance.",
                                 rp.plot_residuals(self.residuals, self.tol, fig_dir / "residuals.png")))
        self.extra_plots(fig_dir)

    def extra_plots(self, fig_dir):
        """Hook for mode-specific figures."""

    def extra_summary(self):
        """Hook: mode-specific HTML to put under the summary. Returns a string."""
        return ""

    # ------------------------------------------------------------------- html
    @staticmethod
    def _table(df, float_fmt="{:.4g}"):
        return df.to_html(index=False, border=0, classes="tbl",
                          float_format=lambda x: float_fmt.format(x), na_rep="")

    @staticmethod
    def _img(path):
        data = base64.b64encode(Path(path).read_bytes()).decode()
        return f'<img src="data:image/png;base64,{data}">'

    def _summary_rows(self):
        best = self.best
        rows = [("Run", self.run_name),
                ("Project", self.project),
                ("Config", self.toml_path.name),
                ("Mode", self.mode_title),
                ("Algorithm", self.s.get("algorythm", "")),
                ("Objective function", self.objective_name),
                ("Model runs", self.stop["runs"]),
                (f"Best {self.objective_name} (m)", f"{self.best_obj:.4g}"),
                ("Best iteration", int(best["iteration"])),
                ("Acceptance tolerance (m)", f"{self.tol:.4g}  [{self.tol_source}]"),
                ("Acceptable runs", len(self.acc))]
        if self.fit:
            rows += [("Bias (m)", f"{self.fit['bias_m']:+.4f}"),
                     ("MAE (m)", f"{self.fit['mae_m']:.4f}"),
                     ("Max |error| (m)", f"{self.fit['max_abs_m']:.4f}"),
                     ("Observation points", self.fit["points"])]
        return rows

    def write_html(self):
        """Assembles report.html (figures embedded) in the report folder."""
        e = html.escape
        parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{e(self.run_name)}</title>"
                 f"<style>{CSS}</style></head><body>",
                 f"<h1>{e(self.mode_title)} report: {e(self.project)}</h1>",
                 f"<p class='note'>Run {e(self.run_name)}. Report created {datetime.now():%Y-%m-%d %H:%M}.</p>"]

        parts.append("<h2>Summary</h2><table class='tbl'>")
        for k, v in self._summary_rows():
            parts.append(f"<tr><th style='text-align:left'>{e(str(k))}</th><td style='text-align:left'>{e(str(v))}</td></tr>")
        parts.append("</table>")
        parts.append(f"<p>{e(self.stop['message'])}</p>")
        parts.append(self.extra_summary())

        if self.flags:
            for f in self.flags:
                parts.append(f"<div class='flag'>{e(f)}</div>")
        else:
            parts.append("<div class='ok'>No bound or sample-size warnings.</div>")
        for n in self.notes:
            parts.append(f"<p class='note'>{e(n)}</p>")

        parts.append("<h2>Calibrated parameters</h2>")
        parts.append("<p class='note'>Acceptable range = values among runs whose objective is within the tolerance of "
                     "the best. It reflects only the runs the optimizer tried, so it is a lower bound on the true spread.</p>")
        parts.append(self._table(self.ranges, "{:.5g}"))

        for title, caption, path in self.figures:
            parts.append(f"<h2>{e(title)}</h2><p class='note'>{e(caption)}</p>{self._img(path)}")

        if "worst_points" in self.tables:
            parts.append("<h2>Largest residuals</h2>" + self._table(self.tables["worst_points"], "{:.4f}"))
        parts.append("<h2>Ten best runs</h2>" + self._table(self.tables["best_runs"], "{:.5g}"))

        if self.plan_meta:
            parts.append("<h2>HEC-RAS plan</h2><p class='note'>Read from the project's plan HDF as it is now; "
                         "if the model has been run again since this run, it may differ.</p><table class='tbl'>")
            for k, v in self.plan_meta.items():
                parts.append(f"<tr><th style='text-align:left'>{e(k)}</th><td style='text-align:left'>{e(v)}</td></tr>")
            parts.append("</table>")

        parts.append("<h2>Calibration settings</h2><table class='tbl'>")
        settings = [("Bounds", self.s.get("bounds")), ("Initial simplex range", self.s.get("i0_guess")),
                    ("max_runs", self.s.get("max_runs")), ("early_stop", self.s.get("early_stop", False)),
                    ("early_stop_tol", self.s.get("early_stop_tol")), ("EPSG", self.s.get("EPSG"))]
        for k, v in settings:
            parts.append(f"<tr><th style='text-align:left'>{e(k)}</th><td style='text-align:left'>{e(str(v))}</td></tr>")
        parts.append("</table></body></html>")

        path = self.report_dir / "report.html"
        path.write_text("\n".join(parts), encoding="utf-8")
        return path

    # -------------------------------------------------------------------- run
    def _new_report_dir(self):
        base = self.report_root / f"{self.project}_{self.run_name}"
        folder, n = base, 0
        while folder.exists():
            n += 1
            folder = base.with_name(f"{base.name}_{n}")
        folder.mkdir(parents=True)
        return folder

    def run(self):
        """Loads, analyzes, plots and writes the report. Returns the report folder."""
        self.load()
        self.analyze()
        self.report_dir = self._new_report_dir()
        self.plot()
        tdir = self.report_dir / "tables"
        tdir.mkdir()
        for name, table in self.tables.items():
            table.to_csv(tdir / f"{name}.csv", index=False)
        self.write_html()
        print(f"Report written to {self.report_dir}")
        return self.report_dir


class ObservedReport(CalibrationReport):
    """Discharge was fixed (measured); the calibrated quantities are roughness (and slopes)."""

    mode_title = "Calibration to observed discharge"

    def extra_summary(self):
        q = self.best.get(self.s.get("Q_params", [None])[0]) if self.s.get("Q_params") else None
        if q is None or pd.isna(q):
            return ""
        return (f"<p class='note'>Discharge was fixed at {q:.4g} m<sup>3</sup>/s ({cms_to_cfs(q):.4g} cfs). "
                "The calibrated values are conditional on that measured discharge; its own uncertainty is not "
                "included in the ranges below.</p>")


class IndirectReport(CalibrationReport):
    """Discharge was calibrated along with roughness; the discharge range is the main result."""

    mode_title = "Indirect discharge calibration"

    def _q_col(self):
        return self.s["Q_params"][0]

    def extra_plots(self, fig_dir):
        q_col = self._q_col()
        n_params = [p for p in self.params if p != q_col and p not in ("us_fs", "ds_fs")]
        if q_col in self.iterations.columns and n_params:
            self.figures.append(("Discharge vs roughness",
                                 "Discharge and roughness trade off against each other. Outlined points are within the "
                                 "tolerance of the best run; a diagonal band means many combinations fit the marks.",
                                 rp.plot_q_vs_n(self.iterations, n_params, q_col, self.best, self.tol,
                                                fig_dir / "q_vs_n.png")))

    def extra_summary(self):
        q_col = self._q_col()
        if q_col not in self.acc.columns:
            return ""
        qb = float(self.best[q_col])
        qlo, qhi = float(self.acc[q_col].min()), float(self.acc[q_col].max())
        return ("<h2>Discharge result</h2><table class='tbl'>"
                "<tr><th></th><th>m<sup>3</sup>/s</th><th>cfs</th><th>vs best</th></tr>"
                f"<tr><th>Best</th><td>{qb:.4g}</td><td>{cms_to_cfs(qb):.4g}</td><td></td></tr>"
                f"<tr><th>Acceptable low</th><td>{qlo:.4g}</td><td>{cms_to_cfs(qlo):.4g}</td>"
                f"<td>{(qlo - qb) / qb * 100:+.1f}%</td></tr>"
                f"<tr><th>Acceptable high</th><td>{qhi:.4g}</td><td>{cms_to_cfs(qhi):.4g}</td>"
                f"<td>{(qhi - qb) / qb * 100:+.1f}%</td></tr></table>"
                f"<p class='note'>Based on {len(self.acc)} run(s) within {self.tol:.3g} m of the best objective.</p>")


def make_report(output_dir, input_dir=None, config_name=None, report_root=None, tol_m=None):
    """Builds the right report object for a finished run from its saved config snapshot."""
    out, inp = rd.resolve_run_folders(output_dir, input_dir)
    _, s = rd.load_settings(rd.find_snapshot_toml(inp, config_name))
    if s.get("cal_indirect"):
        cls = IndirectReport
    elif s.get("cal_observed") or s.get("cal_EG_slope"):
        cls = ObservedReport
    else:
        raise NotImplementedError("Reports exist for calibration runs only (cal_observed, cal_indirect, cal_EG_slope).")
    return cls(out, inp, config_name, report_root, tol_m)


