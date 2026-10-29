"""Data loading and analysis for Q2Dpy calibration reports.

No plotting here, and no dependency on config.py, so a report can be built from a
finished run's folders alone (Output/<run>, plus its Input/<run> snapshot).
"""
import re
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

# sections of the TOML whose keys are flattened into one settings dict (same as config.py, plus [report])
FLAT_SECTIONS = ("mode", "calibration", "options", "ratecurve", "sim_event", "labels", "report")
BOUND_FRACTION = 0.05          # a best value this close (fraction of the bound range) to a bound is flagged
FALLBACK_TOL_FRACTION = 0.10   # acceptance tolerance when none is configured: this fraction of the best objective


# ------------------------------------------------------------------ run folders
def resolve_run_folders(output_dir, input_dir=None):
    """Returns (output run folder, input snapshot folder).

    By default the snapshot is the sibling Input/<same run name> of the Output folder.
    """
    output_dir = Path(output_dir).resolve()
    if input_dir is None:
        input_dir = output_dir.parent.parent / "Input" / output_dir.name
    return output_dir, Path(input_dir)


def find_snapshot_toml(input_dir, config_name=None):
    """Finds the config TOML copied into the run's Input snapshot folder."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input snapshot folder not found: {input_dir}")
    if config_name:
        path = input_dir / config_name
        if not path.is_file():
            raise FileNotFoundError(f"{config_name} not found in {input_dir}")
        return path
    tomls = sorted(input_dir.glob("*.toml"))
    if not tomls:
        raise FileNotFoundError(f"No .toml snapshot in {input_dir}")
    if len(tomls) > 1:
        names = ", ".join(t.name for t in tomls)
        raise ValueError(f"Several .toml files in {input_dir} ({names}); pass config_name")
    return tomls[0]


def load_settings(toml_path):
    """Reads a config TOML. Returns (raw nested dict, flattened dict like config.py's module names)."""
    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)
    flat = {k: v for k, v in raw.items() if not isinstance(v, dict)}
    for sec in FLAT_SECTIONS:
        flat.update(raw.get(sec, {}))
    return raw, flat


# ------------------------------------------------------------------- data files
def load_iterations(path):
    """Reads model_iterations.csv."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Iterations file not found: {path}")
    df = pd.read_csv(path)
    missing = [c for c in ("iteration", "Obj_Func_Value") if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} is missing column(s): {missing}")
    return df.reset_index(drop=True)


def load_profiles(path):
    """Reads wse_profiles_output.csv, sorted by channel distance. Returns None if the file is absent."""
    path = Path(path)
    if not path.is_file():
        return None
    df = pd.read_csv(path)
    if "Channel_Distance" in df.columns:
        df = df.sort_values("Channel_Distance").reset_index(drop=True)
    return df


def profile_columns(profiles):
    """Names of the per-iteration columns (I1, I2, ...) of a profiles table."""
    return [c for c in profiles.columns if re.fullmatch(r"I\d+", c)]


def read_plan_metadata(raw):
    """Plan information from the plan HDF (HEC-RAS version, plan/geometry/flow names, times).
    Returns a dict, or None if h5py or the file is unavailable."""
    try:
        import h5py
        ras = raw["ras"]
        path = Path(raw["paths"]["directory"]) / "RAS_files" / f"{ras['prj']}.{ras['plan']}.hdf"
        if not path.is_file():
            return None

        def txt(v):
            return v.decode() if isinstance(v, bytes) else str(v)

        with h5py.File(path, "r") as f:
            info = f["Plan Data/Plan Information"].attrs
            out = {
                "Project": txt(info["Project Title"]),
                "Plan": txt(info["Plan Name"]),
                "Geometry": txt(info["Geometry Title"]),
                "Flow": txt(info["Flow Title"]),
                "Simulation start": txt(info["Simulation Start Time"]),
                "Simulation end": txt(info["Simulation End Time"]),
                "Computation time step": txt(info["Computation Time Step Base"]),
            }
            try:
                out["HEC-RAS version"] = txt(f["Results/Summary/Compute Processes"][0][4])
            except Exception:
                pass
        return out
    except Exception:
        return None


# ------------------------------------------------------------------- parameters
def optimizer_parameter_order(s):
    """Calibrated parameter names in the order the optimizer used them (matches `bounds`)."""
    names = []
    if s.get("cal_EG_slope"):
        names += list(s.get("FS_params", []))
    if s.get("cal_observed") or s.get("cal_indirect"):
        names += list(s.get("Man_n_params", []))
    if s.get("independent_structures"):
        names.append("Structures")
    if s.get("cal_indirect"):
        names += list(s.get("Q_params", []))[:1]
    return names


def calibrated_parameters(s, df):
    """Returns (parameter columns to report on, {name: (low, high)} bounds or {}).

    Parameters that never changed during the run are dropped (unless none changed).
    Bounds are only returned when their count matches the optimizer parameter order.
    """
    ordered = optimizer_parameter_order(s)
    bounds = s.get("bounds", [])
    bounds_map = {}
    if ordered and len(ordered) == len(bounds):
        bounds_map = {n: (float(b[0]), float(b[1])) for n, b in zip(ordered, bounds)}

    present = [n for n in ordered if n in df.columns]
    varying = [n for n in present if df[n].nunique() > 1]
    params = varying if varying else present
    return params, {n: bounds_map[n] for n in params if n in bounds_map}


# --------------------------------------------------------------------- analysis
def best_run(df):
    """Row (Series) of the lowest objective value."""
    return df.loc[df["Obj_Func_Value"].idxmin()]


def best_so_far(df):
    """Running minimum of the objective."""
    return np.minimum.accumulate(df["Obj_Func_Value"].to_numpy())


def resolve_tolerance(tol_arg, s, best_obj):
    """Acceptance tolerance (same units as the objective). Returns (value, where it came from)."""
    if tol_arg is not None:
        return float(tol_arg), "argument"
    cfg = s.get("report_tol_m")
    if cfg is not None:
        return float(cfg), "config [report] report_tol_m"
    return FALLBACK_TOL_FRACTION * float(best_obj), f"fallback ({int(FALLBACK_TOL_FRACTION * 100)}% of best objective)"


def acceptable_runs(df, best_obj, tol):
    """Runs whose objective is within `tol` of the best run."""
    return df[df["Obj_Func_Value"] <= best_obj + tol]


def parameter_ranges(acc, best_row, params, bounds_map):
    """Best value and acceptable range of each parameter."""
    rows = []
    for p in params:
        lo, hi = bounds_map.get(p, (np.nan, np.nan))
        rows.append({"parameter": p, "best": best_row[p],
                     "accepted_min": acc[p].min(), "accepted_max": acc[p].max(),
                     "bound_low": lo, "bound_high": hi})
    return pd.DataFrame(rows)


def bound_flags(best_row, params, bounds_map):
    """Messages for parameters whose best value sits near a bound."""
    flags = []
    for p in params:
        if p not in bounds_map:
            continue
        lo, hi = bounds_map[p]
        span = hi - lo
        if span <= 0:
            continue
        pos = (best_row[p] - lo) / span
        if pos < BOUND_FRACTION:
            flags.append(f"{p} = {best_row[p]:.4g} is within {int(BOUND_FRACTION * 100)}% of its lower bound ({lo:g}); "
                         "the true value may be lower.")
        elif pos > 1 - BOUND_FRACTION:
            flags.append(f"{p} = {best_row[p]:.4g} is within {int(BOUND_FRACTION * 100)}% of its upper bound ({hi:g}); "
                         "the true value may be higher.")
    return flags


def stop_summary(df, s):
    """How the optimization ended, as a dict of facts and a short message."""
    n_runs = len(df)
    early = bool(s.get("early_stop", False))
    tol = s.get("early_stop_tol")
    last_std = None
    if "Obj_Std" in df.columns and df["Obj_Std"].notna().any():
        last_std = float(df["Obj_Std"].dropna().iloc[-1])

    if early and tol is not None and last_std is not None and last_std < tol:
        msg = f"Stopped early: the last Obj_Std ({last_std:.2e}) fell below early_stop_tol ({tol:g})."
    elif early:
        msg = "Early stopping was on, but the final Obj_Std did not fall below the tolerance; the run ended on its own limits."
    else:
        msg = "Early stopping was off; the run ended on the optimizer's own tolerance or max_runs."
    return {"runs": n_runs, "early_stop": early, "early_stop_tol": tol, "last_obj_std": last_std, "message": msg}


def residual_table(profiles, iteration):
    """Modeled minus measured WSE at each observation point for one iteration. None if unavailable."""
    if profiles is None:
        return None
    col = f"I{int(iteration)}"
    if col not in profiles.columns:
        return None
    out = profiles[[c for c in ("ID", "Cell_Index", "Channel_Distance", "Elev_m") if c in profiles.columns]].copy()
    out["Modeled"] = profiles[col]
    out["Residual"] = profiles[col] - profiles["Elev_m"]
    return out


def fit_statistics(res):
    """Bias, RMSE, MAE, maximum error and spread of a residual series (meters)."""
    r = np.asarray(res, float)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return {}
    return {"points": int(len(r)),
            "bias_m": float(r.mean()),
            "rmse_m": float(np.sqrt(np.mean(r ** 2))),
            "mae_m": float(np.mean(np.abs(r))),
            "max_abs_m": float(np.max(np.abs(r))),
            "std_m": float(r.std(ddof=1)) if len(r) > 1 else float("nan")}


def worst_points(res_df, n=5):
    """The n observation points with the largest absolute residual."""
    return res_df.reindex(res_df["Residual"].abs().sort_values(ascending=False).index).head(n)