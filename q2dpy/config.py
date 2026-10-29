"""Site config loader for Q2Dpy.

Reads a TOML site config and exposes its values as module-level names, so the
rest of the code can keep using `import config` and `config.<name>`.

Per-run folders: call start_run() once at the start of a run. It creates
Input/<run name> (a snapshot of the input files, for logging) and
Output/<run name> (everything the run writes), and points the output paths at it.
"""
import shutil
import tomllib
from datetime import datetime
from pathlib import Path

import units

# ======================= EDIT THIS LINE TO CHOOSE PROJECT =======================
CONFIG_NAME = "template.toml"
# =================================================================================

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"
CONFIG_PATH = CONFIGS_DIR / CONFIG_NAME

if not CONFIG_PATH.is_file():
    raise SystemExit(f"Config file not found: {CONFIG_PATH}")

with open(CONFIG_PATH, "rb") as _f:
    _raw = tomllib.load(_f)

CFS_TO_CMS = units.CFS_TO_CMS

# Top-level keys and the keys of these sections become module-level names.
_FLAT_SECTIONS = (
    "mode", "calibration", "options", "ratecurve", "sim_event", "labels",
)

_flat = {k: v for k, v in _raw.items() if not isinstance(v, dict)}
for _sec in _FLAT_SECTIONS:
    _flat.update(_raw.get(_sec, {}))
globals().update(_flat)


# -------------------------------------------------------- tuple-ify the lists
bounds = [tuple(x) for x in bounds]
i0_guess = [tuple(x) for x in i0_guess]


# ------------------------------------------------------------- friction slopes
friction_slope = [upstream_friction_slope, downstream_friction_slope]


# ----------------------------------------------------------------- directories
Directory = Path(_raw["paths"]["directory"])
ras_directory = Directory / "RAS_files"
gis_directory = Directory / "GIS"
input_directory = Directory / "Input"
output_root = Directory / "Output"          # parent of all per-run output folders


# ----------------------------------------------------------------- RAS project
_ras = _raw["ras"]
prj = _ras["prj"]
prj_filename = ras_directory / f"{prj}.prj"
geom_filename = ras_directory / f"{prj}.{_ras['geom']}"
ghdf_filename = ras_directory / f"{prj}.{_ras['geom']}.hdf"
flow_filename = ras_directory / f"{prj}.{_ras['flow']}"
plan_filename = ras_directory / f"{prj}.{_ras['plan']}"
phdf_filename = ras_directory / f"{prj}.{_ras['plan']}.hdf"
lchdf_filename = ras_directory / _ras["landcover"]


# ------------------------------------------------------- input / output files
_in = _raw["inputs"]
grid_filename = gis_directory / _in["grid_filename"]
terrain_raster = gis_directory / _in["terrain_raster"]
wse_filename = input_directory / _in["wse_filename"]
trendline = input_directory / _in["trendline"]
q_list = input_directory / _in["q_list"]

_out = _raw["outputs"]


def _build_output_paths(out_dir):
    """(Re)builds every output path under out_dir."""
    global output_directory, geojson_directory
    global simplex_filename, iterations_filename, wse_prof_filename
    global rating_curve_filename, batch_filename
    output_directory = out_dir
    geojson_directory = out_dir / "GeoJSONs"
    simplex_filename = out_dir / _out["simplex_filename"]
    iterations_filename = out_dir / _out["iterations_filename"]
    wse_prof_filename = out_dir / _out["wse_prof_filename"]
    rating_curve_filename = out_dir / _out["rating_curve_filename"]
    batch_filename = out_dir / _out["batch_filename"]


# before start_run() the outputs point at the Output root (so importing config alone is harmless)
_build_output_paths(output_root)

run_name = None
run_input_directory = None


# ------------------------------------------------------ derived discharge vals
Q_params_vals = [round(Q_params_cfs * CFS_TO_CMS, 3)]
min_q = round(min_cfs * CFS_TO_CMS, 3)
max_q = round(max_cfs * CFS_TO_CMS, 3)


# ------------------------------------------------------------------ run folders
def run_label():
    """Mode part of the run name, e.g. 'cal_observed', 'cal_observed_EG', 'cal_indirect_batch'."""
    if cal_observed:
        label = "cal_observed"
    elif cal_indirect:
        label = "cal_indirect"
    elif gen_ratecurv:
        label = "gen_ratecurv"
    elif sim_event:
        label = "sim_event"
    elif cal_EG_slope:
        label = "cal_EG_slope"
    else:
        label = "run"

    if cal_EG_slope and label not in ("cal_EG_slope", "run"):
        label += "_EG"
    if batch_process is True and label.startswith("cal_"):
        label += "_batch"
    return label


def start_run():
    """Creates this run's Input and Output subfolders (same name in both) and points
    the output paths at the new Output subfolder. Call once, after validate()."""
    global run_name, run_input_directory

    base = f"{datetime.now():%Y%m%d}_{run_label()}"
    name, n = base, 0
    while (input_directory / name).exists() or (output_root / name).exists():
        n += 1
        name = f"{base}_{n}"

    run_name = name
    run_input_directory = input_directory / name
    run_input_directory.mkdir(parents=True)
    out_dir = output_root / name
    out_dir.mkdir(parents=True)
    _build_output_paths(out_dir)

    print(f"Run: {run_name}")
    print(f"  Input snapshot : {run_input_directory}")
    print(f"  Outputs        : {output_directory}")
    return run_name


def snapshot_inputs():
    """Logs what the run used: copies the config TOML and the files currently in the
    Input folder (not the earlier run subfolders) into this run's Input subfolder.
    Call after any step that edits an input file (e.g. cell index lookup)."""
    shutil.copy2(CONFIG_PATH, run_input_directory / CONFIG_PATH.name)
    copied = 0
    for p in sorted(input_directory.iterdir()):
        if p.is_file():
            shutil.copy2(p, run_input_directory / p.name)
            copied += 1
    print(f"Snapshot: {CONFIG_PATH.name} and {copied} input file(s) copied to {run_input_directory}")


# ------------------------------------------------------------------ validation
def _get(name, default=None):
    """Optional config value (older TOMLs may not define every key)."""
    return globals().get(name, default)


def _initial_vector():
    """Starting parameter vector, built the same way calibration.optimize_model builds it.
    Used to check the bounds. Returns None when no calibration mode is on."""
    if cal_observed is True:
        if cal_EG_slope is True:
            return list(friction_slope)
        vec = list(Man_n_vals)
        if independent_structures is True:
            vec.append(Man_n_vals[0])
        return vec
    if cal_indirect is True:
        vec = list(friction_slope) if cal_EG_slope is True else []
        vec.extend(Man_n_vals)
        if independent_structures is True:
            vec.append(Man_n_vals[0])
        vec.append(Q_params_vals[0])
        return vec
    if cal_EG_slope is True:
        return list(friction_slope)
    return None


def _ras_datetime(date_str, time_str):
    """Parses '07JUN2023' + '03:00'. HEC-RAS also allows '24:00' (midnight of the next day)."""
    from datetime import timedelta
    if time_str == "24:00":
        return datetime.strptime(date_str.upper(), "%d%b%Y") + timedelta(days=1)
    return datetime.strptime(f"{date_str.upper()} {time_str}", "%d%b%Y %H:%M")


def validate():
    """Fail early on config problems. Call once at the start of main.
    Errors stop the run; warnings are printed and the run continues."""
    errors, warnings = [], []
    cal_modes = (cal_observed, cal_indirect, cal_EG_slope)
    is_cal = any(m is True for m in cal_modes)

    # ---- files
    for label, p in (("project", prj_filename), ("geometry", geom_filename),
                     ("flow", flow_filename), ("plan", plan_filename),
                     ("land cover HDF", lchdf_filename)):
        if not p.is_file():
            errors.append(f"Missing {label} file: {p}")
    if not phdf_filename.is_file():
        errors.append(f"Missing plan results HDF: {phdf_filename}. Run the plan once in the "
                      "HEC-RAS GUI, then close HEC-RAS, before automating.")
    if not wse_filename.is_file() and (is_cal or gen_ratecurv is True or sim_event is True):
        errors.append(f"Missing observation file: {wse_filename}")
    if _get("find_cell_index") is True and not grid_filename.is_file():
        errors.append(f"find_cell_index needs the mesh shapefile: {grid_filename}")
    if _get("export_shapefile") is True and not terrain_raster.is_file():
        errors.append(f"export_shapefile needs the terrain raster: {terrain_raster}")
    if gen_ratecurv is True and _get("use_Q_list") is True and not q_list.is_file():
        errors.append(f"use_Q_list is on but the file is missing: {q_list}")

    # ---- run mode combinations
    if not any((cal_observed, cal_indirect, cal_EG_slope, gen_ratecurv, sim_event)):
        errors.append("No run mode is true in [mode].")
    if cal_observed is True and cal_indirect is True:
        errors.append("cal_observed and cal_indirect cannot both be true.")
    if gen_ratecurv is True and sim_event is True:
        errors.append("gen_ratecurv and sim_event cannot both be true.")
    if (gen_ratecurv is True or sim_event is True) and is_cal:
        errors.append("gen_ratecurv / sim_event cannot be combined with a calibration mode.")
    if batch_process is True and not (cal_observed is True and cal_indirect is not True
                                      and cal_EG_slope is not True):
        errors.append("batch_process currently supports cal_observed only "
                      "(not cal_indirect or cal_EG_slope).")
    if _get("get_inst_q") is True and sim_event is not True:
        warnings.append("get_inst_q only affects sim_event; it is ignored in this mode.")

    # ---- calibration settings
    if is_cal:
        if len(Man_n_vals) != len(Man_n_params):
            errors.append(f"Man_n_vals ({len(Man_n_vals)}) and Man_n_params "
                          f"({len(Man_n_params)}) differ in length.")
        if any(v <= 0 for v in Man_n_vals):
            errors.append("Man_n_vals must all be greater than 0.")
        if str(objective_function).upper() not in ("RMSE", "MAE"):
            errors.append(f"Unknown objective_function: {objective_function} (use RMSE or MAE).")
        if str(algorythm).lower() not in ("nelder-mead", "sce-ua"):
            errors.append(f"Unknown algorythm: {algorythm}")
        if not isinstance(max_runs, int) or max_runs < 1:
            errors.append("max_runs must be a whole number of at least 1.")
        if create_i0_simplex is True and str(algorythm).lower() == "sce-ua":
            warnings.append("create_i0_simplex is documented for Nelder-Mead only.")

        if cal_EG_slope is True:
            fs = list(FS_params)
            if not fs or any(f not in ("us_fs", "ds_fs") for f in fs):
                errors.append('FS_params must be "us_fs", "ds_fs" or both when cal_EG_slope is on.')
            elif len(fs) == 2 and fs[0] != "us_fs":
                errors.append("FS_params: us_fs must come first when both are used.")
        if any(s <= 0 for s in friction_slope if s is not None):
            errors.append("Friction slopes must be greater than 0.")

        if early_stop is True:
            tol = _get("early_stop_tol")
            if tol is None or tol <= 0:
                errors.append("early_stop = true requires early_stop_tol > 0 in [calibration].")

        # bounds and starting simplex
        vec = _initial_vector()
        if len(bounds) != len(i0_guess):
            errors.append(f"bounds ({len(bounds)}) and i0_guess ({len(i0_guess)}) differ in length.")
        if vec is not None and len(bounds) != len(vec):
            errors.append(f"bounds has {len(bounds)} row(s) but this mode calibrates {len(vec)} "
                          "parameter(s). Order: friction slopes, Manning's n regions, "
                          "structure n (if independent), discharge (cal_indirect).")
        for i, b in enumerate(bounds):
            if len(b) != 2 or not b[0] < b[1]:
                errors.append(f"bounds row {i + 1} must be (low, high) with low < high: {b}")
        for i, g in enumerate(i0_guess):
            if len(g) != 2 or g[0] > g[1]:
                errors.append(f"i0_guess row {i + 1} must be (low, high) with low <= high: {g}")
        if vec is not None and len(bounds) == len(vec) and not errors:
            for i, (v, (lo, hi)) in enumerate(zip(vec, bounds)):
                if not lo <= v <= hi:
                    errors.append(f"Starting value {v} for parameter {i + 1} is outside "
                                  f"its bounds ({lo}, {hi}).")
            if len(i0_guess) == len(bounds):
                for i, ((glo, ghi), (lo, hi)) in enumerate(zip(i0_guess, bounds)):
                    if glo < lo or ghi > hi:
                        warnings.append(f"i0_guess row {i + 1} ({glo}, {ghi}) extends outside "
                                        f"its bounds ({lo}, {hi}).")

        if structures is False and independent_structures:
            errors.append("independent_structures requires structures = true.")
        if cal_indirect is True and Q_params_cfs <= 0:
            errors.append("Q_params_cfs must be greater than 0.")

    # ---- rating curve
    if gen_ratecurv is True:
        if _get("use_Q_list") is not True:
            if not max_cfs > min_cfs:
                errors.append("max_cfs must be greater than min_cfs.")
            if not isinstance(q_divisions, int) or q_divisions < 1:
                errors.append("q_divisions must be a whole number of at least 1.")
    if adjust_n_rating and (gen_ratecurv is True):
        lens = {len(a), len(b), len(n_regions), len(function_type), len(max_n), len(min_n)}
        if len(lens) != 1:
            errors.append("a, b, n_regions, function_type, max_n and min_n must be the same length.")
        if any(lo > hi for lo, hi in zip(min_n, max_n)):
            errors.append("min_n is larger than max_n for at least one region.")
        bad = [f for f in function_type if f not in ("linear", "log", "exp", "power", "hyper")]
        if bad:
            errors.append(f"Unknown function_type value(s): {bad}")

    # ---- single event / simulation window
    if sim_event is True or gen_ratecurv is True:
        if _get("export_geojsons") and not _get("export_shapefile"):
            errors.append("export_geojsons requires export_shapefile = true.")
    if set_datetime is True:
        try:
            t0 = _ras_datetime(start_date, start_time)
            t1 = _ras_datetime(end_date, end_time)
            if t1 <= t0:
                errors.append("The simulation end must be after the start.")
        except (ValueError, TypeError):
            errors.append("start_date/end_date must look like 07JUN2023 and "
                          "start_time/end_time like 03:00.")
    if change_sim_time is True and sim_time_hr < 1:
        errors.append("sim_time_hr must be at least 1.")

    # ---- general
    if not str(hec_version).isdigit():
        errors.append(f'hec_version should be digits such as "701", got {hec_version!r}.')
    if not str(EPSG).upper().startswith("EPSG:"):
        errors.append(f'EPSG should look like "EPSG:6514", got {EPSG!r}.')
    tol_m = _raw.get("report", {}).get("report_tol_m")
    if tol_m is not None and tol_m <= 0:
        errors.append("[report] report_tol_m must be greater than 0.")

    for w in warnings:
        print(f"Config warning: {w}")
    if errors:
        raise SystemExit("Config errors:\n  - " + "\n  - ".join(errors))


