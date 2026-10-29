"""Figures for Q2Dpy calibration reports (matplotlib, saved as PNG)."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .data import best_so_far, profile_columns

DPI = 150


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return Path(path)


def _log_if_wide(ax, values, ratio=50):
    v = np.asarray(values, float)
    v = v[np.isfinite(v) & (v > 0)]
    if len(v) > 1 and v.max() / v.min() > ratio:
        ax.set_yscale("log")


def plot_convergence(df, objective_name, early_stop_tol, path):
    """Objective vs iteration with best-so-far, plus the Obj_Std trace when it was logged."""
    has_std = "Obj_Std" in df.columns and df["Obj_Std"].notna().any()
    if has_std:
        fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    else:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax2 = None

    it = df["iteration"]
    obj = df["Obj_Func_Value"]
    ax.plot(it, obj, "-o", color="0.6", ms=3, lw=0.8, label="each model run")
    ax.step(it, best_so_far(df), where="post", color="tab:blue", lw=1.8, label="best so far")
    i_best = obj.idxmin()
    ax.plot(it[i_best], obj[i_best], "*", color="tab:red", ms=14, label=f"best (iteration {int(it[i_best])})")
    ax.set_ylabel(f"{objective_name} (m)")
    ax.set_title("Convergence")
    _log_if_wide(ax, obj)
    ax.legend()
    ax.grid(alpha=0.3)

    if has_std:
        ax2.plot(it, df["Obj_Std"], "-o", color="tab:green", ms=3, lw=1)
        if early_stop_tol:
            ax2.axhline(early_stop_tol, color="tab:red", ls="--", label=f"early_stop_tol = {early_stop_tol:g}")
            ax2.legend()
        ax2.set_yscale("log")
        ax2.set_ylabel("Obj_Std (m)\nstd of last 2 simplexes")
        ax2.set_xlabel("iteration")
        ax2.grid(alpha=0.3)
    else:
        ax.set_xlabel("iteration")
    return _save(fig, path)


def plot_parameters_vs_iteration(df, params, bounds_map, path):
    """One panel per calibrated parameter against iteration; best run and bounds marked."""
    fig, axes = plt.subplots(len(params), 1, figsize=(8, 2.4 * len(params) + 1), sharex=True, squeeze=False)
    it = df["iteration"]
    i_best = df["Obj_Func_Value"].idxmin()
    for ax, p in zip(axes[:, 0], params):
        ax.plot(it, df[p], "-o", ms=3, lw=0.9, color="tab:blue")
        ax.plot(it[i_best], df[p][i_best], "*", color="tab:red", ms=13)
        if p in bounds_map:
            lo, hi = bounds_map[p]
            ax.axhline(lo, color="0.5", ls="--", lw=0.8)
            ax.axhline(hi, color="0.5", ls="--", lw=0.8)
        ax.set_ylabel(p)
        ax.grid(alpha=0.3)
    axes[0, 0].set_title("Parameters vs iteration (star = best run, dashed = bounds)")
    axes[-1, 0].set_xlabel("iteration")
    return _save(fig, path)


def plot_objective_vs_parameter(df, params, objective_name, best_row, tol, path):
    """Objective against each parameter, colored by iteration. The dashed line is best + tolerance."""
    n = len(params)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.6 * ncols, 3.6 * nrows), squeeze=False, layout="constrained")
    obj = df["Obj_Func_Value"]
    sc = None
    for ax, p in zip(axes.ravel(), params):
        sc = ax.scatter(df[p], obj, c=df["iteration"], cmap="viridis", s=18)
        ax.plot(best_row[p], best_row["Obj_Func_Value"], "*", color="tab:red", ms=14)
        ax.axhline(best_row["Obj_Func_Value"] + tol, color="tab:red", ls="--", lw=1)
        ax.set_xlabel(p)
        ax.set_ylabel(f"{objective_name} (m)")
        _log_if_wide(ax, obj)
        ax.grid(alpha=0.3)
    for ax in axes.ravel()[n:]:
        ax.set_visible(False)
    fig.colorbar(sc, ax=axes.ravel().tolist(), label="iteration", shrink=0.8)
    fig.suptitle("Objective vs parameter (dashed = best + tolerance; points below it are acceptable)")
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return Path(path)


def plot_q_vs_n(df, n_params, q_col, best_row, tol, path):
    """Discharge against each Manning's n, colored by objective, acceptable runs outlined."""
    n = len(n_params)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.6 * ncols, 3.8 * nrows), squeeze=False, layout="constrained")
    best_obj = best_row["Obj_Func_Value"]
    vmax = best_obj + 5 * tol
    acc = df["Obj_Func_Value"] <= best_obj + tol
    sc = None
    for ax, p in zip(axes.ravel(), n_params):
        sc = ax.scatter(df[p], df[q_col], c=df["Obj_Func_Value"], cmap="viridis_r", s=22,
                        vmin=best_obj, vmax=vmax)
        ax.scatter(df.loc[acc, p], df.loc[acc, q_col], facecolors="none", edgecolors="k", s=60, lw=1,
                   label="acceptable")
        ax.plot(best_row[p], best_row[q_col], "*", color="tab:red", ms=14, label="best")
        ax.set_xlabel(p)
        ax.set_ylabel(f"{q_col} (m$^3$/s)")
        ax.grid(alpha=0.3)
    axes.ravel()[0].legend()
    for ax in axes.ravel()[n:]:
        ax.set_visible(False)
    fig.colorbar(sc, ax=axes.ravel().tolist(), label="objective (m), clipped at best + 5 x tolerance", shrink=0.8)
    fig.suptitle("Discharge vs roughness trade-off")
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return Path(path)


def plot_profile(profiles, best_iteration, path):
    """Measured WSE points, every iteration's modeled profile (faint) and the best profile."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = profiles["Channel_Distance"]
    for c in profile_columns(profiles):
        ax.plot(x, profiles[c], color="0.75", lw=0.6, alpha=0.5)
    best_col = f"I{int(best_iteration)}"
    ax.plot(x, profiles[best_col], color="tab:blue", lw=2, label=f"best model (iteration {int(best_iteration)})")
    ax.plot(x, profiles["Elev_m"], "o", color="tab:red", ms=6, label="measured")
    ax.plot([], [], color="0.75", label="other iterations")
    ax.set_xlabel("Channel distance (m)")
    ax.set_ylabel("Water surface elevation (m)")
    ax.set_title("Water surface profile")
    ax.legend()
    ax.grid(alpha=0.3)
    return _save(fig, path)


def plot_residuals(res_df, tol, path):
    """Residuals (modeled - measured) against channel distance, and their distribution."""
    fig, (ax, axh) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"width_ratios": [3, 1]}, sharey=True)
    x = res_df["Channel_Distance"]
    r = res_df["Residual"]
    ax.axhspan(-tol, tol, color="tab:green", alpha=0.12, label=f"+/- tolerance ({tol:g} m)")
    ax.axhline(0, color="k", lw=0.8)
    ax.plot(x, r, "o", color="tab:blue")
    if "ID" in res_df.columns:
        for _, row in res_df.reindex(r.abs().sort_values(ascending=False).index).head(3).iterrows():
            ax.annotate(str(row["ID"]), (row["Channel_Distance"], row["Residual"]),
                        textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax.set_xlabel("Channel distance (m)")
    ax.set_ylabel("Modeled - measured WSE (m)")
    ax.set_title("Residuals of the best run")
    ax.legend()
    ax.grid(alpha=0.3)
    axh.hist(r, bins=max(5, min(15, len(r) // 2 + 1)), orientation="horizontal", color="tab:blue", alpha=0.7)
    axh.axhline(0, color="k", lw=0.8)
    axh.set_xlabel("count")
    return _save(fig, path)
