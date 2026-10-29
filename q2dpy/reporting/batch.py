"""Report for batch calibrations: plots for each optimization run and a summary of the batch results."""
import html
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pandas as pd

from . import data as rd
from . import plots as rp
from .builder import CalibrationReport, CSS


def split_runs(df):
    """Splits the shared iterations table into one DataFrame per optimization run."""
    if "Batch_Row" in df.columns and df["Batch_Row"].notna().all():
        key = df["Batch_Row"]
    elif "Q(cfs)" in df.columns:
        key = df["Q(cfs)"]
    else:
        raise ValueError("Cannot split the batch: neither Batch_Row nor Q(cfs) is in the iterations file.")
    run_id = (key != key.shift()).cumsum()
    return [sub.reset_index(drop=True) for _, sub in df.groupby(run_id, sort=True)]


def plot_batch_summary(res, params, objective_name, path):
    """Calibrated parameters and final error of every batch row against discharge."""
    res = res.sort_values("Q(cfs)")
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    for p in params:
        ax.plot(res["Q(cfs)"], res[p], "-o", ms=4, lw=0.8, label=p)
    ax.set_ylabel("Calibrated Manning's n")
    ax.set_title("Batch results")
    ax.legend()
    ax.grid(alpha=0.3)
    ax2.plot(res["Q(cfs)"], res["Obj_Func_Value"], "-o", ms=4, lw=0.8, color="tab:red")
    ax2.set_ylabel(f"Final {objective_name} (m)")
    ax2.set_xlabel("Discharge (cfs)")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=rp.DPI)
    plt.close(fig)
    return path


class BatchReport(CalibrationReport):
    """One optimization per row of the observation file (batch_process = true)."""

    mode_title = "Batch calibration"

    def run(self):
        self.load()
        it = self.iterations
        self.params, self.bounds_map = rd.calibrated_parameters(self.s, it)
        if not self.params:
            raise ValueError("No calibrated parameter columns found in the iterations file.")
        runs = split_runs(it)

        bpath = self.output_dir / self.raw["outputs"]["batch_filename"]
        res = pd.read_csv(bpath) if bpath.is_file() else pd.DataFrame([r.iloc[-1] for r in runs])

        rows = []
        for k, sub in enumerate(runs, 1):
            best, last = rd.best_run(sub), sub.iloc[-1]
            row = {"run": k, "Q(cfs)": last.get("Q(cfs)"), "model_runs": len(sub),
                   "best_obj": best["Obj_Func_Value"], "final_obj": last["Obj_Func_Value"]}
            row.update({p: last[p] for p in self.params})
            rows.append(row)
            for msg in rd.bound_flags(last, self.params, self.bounds_map):
                self.flags.append(f"Run {k}: {msg}")
        summary = pd.DataFrame(rows)

        self.report_dir = self._new_report_dir()
        fig_dir = self.report_dir / "figures"
        run_dir = fig_dir / "runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        (self.report_dir / "tables").mkdir(exist_ok=True)
        summary.to_csv(self.report_dir / "tables" / "run_summary.csv", index=False)
        res.to_csv(self.report_dir / "tables" / "batch_results.csv", index=False)

        batch_fig = plot_batch_summary(res, self.params, self.objective_name, fig_dir / "batch_summary.png")
        tol = self.s.get("early_stop_tol")
        run_figs = []
        for k, sub in enumerate(runs, 1):
            conv = rp.plot_convergence(sub, self.objective_name, tol, run_dir / f"run_{k:03d}_convergence.png")
            par = rp.plot_parameters_vs_iteration(sub, self.params, self.bounds_map,
                                                  run_dir / f"run_{k:03d}_parameters.png")
            run_figs.append((conv, par))

        path = self._write_batch_html(summary, batch_fig, runs, run_figs)
        print(f"Report written to {self.report_dir}")
        return self.report_dir

    def _write_batch_html(self, summary, batch_fig, runs, run_figs):
        e = html.escape
        parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{e(self.run_name)}</title>"
                 f"<style>{CSS}</style></head><body>",
                 f"<h1>{e(self.mode_title)} report: {e(self.project)}</h1>",
                 f"<p class='note'>Run {e(self.run_name)}. Report created {datetime.now():%Y-%m-%d %H:%M}.</p>",
                 "<h2>Summary</h2><table class='tbl'>"]
        for k, v in [("Config", self.toml_path.name), ("Algorithm", self.s.get("algorythm", "")),
                     ("Objective function", self.objective_name), ("Optimization runs", len(runs)),
                     ("Model runs (total)", len(self.iterations)),
                     ("early_stop", self.s.get("early_stop", False)),
                     ("early_stop_tol", self.s.get("early_stop_tol"))]:
            parts.append(f"<tr><th style='text-align:left'>{e(str(k))}</th><td style='text-align:left'>{e(str(v))}</td></tr>")
        parts.append("</table>")
        parts.append("<p class='note'>Each batch row is scored at a single observation, so the objective is the "
                     "absolute error at that point.</p>")
        for f in self.flags:
            parts.append(f"<div class='flag'>{e(f)}</div>")
        if not self.flags:
            parts.append("<div class='ok'>No bound warnings.</div>")

        parts.append("<h2>Batch results</h2>" + self._img(batch_fig))
        parts.append(self._table(summary, "{:.5g}"))

        parts.append("<h2>Optimization runs</h2>")
        for k, (sub, (conv, par)) in enumerate(zip(runs, run_figs), 1):
            last = sub.iloc[-1]
            q = last.get("Q(cfs)")
            parts.append(f"<details><summary>Run {k}: Q = {q:.4g} cfs, {len(sub)} model runs, "
                         f"final {e(self.objective_name)} = {last['Obj_Func_Value']:.4g} m</summary>"
                         f"{self._img(conv)}{self._img(par)}</details>")
        parts.append("</body></html>")
        path = self.report_dir / "report.html"
        path.write_text("\n".join(parts), encoding="utf-8")
        return path