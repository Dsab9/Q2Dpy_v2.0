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
def validate():
    """Fail early on obvious config problems. Call once at the start of main."""
    errors = []

    for label, p in (("project", prj_filename), ("geometry", geom_filename),
                     ("flow", flow_filename), ("plan", plan_filename)):
        if not p.is_file():
            errors.append(f"Missing {label} file: {p}")

    if not any((cal_observed, cal_indirect, cal_EG_slope, gen_ratecurv, sim_event)):
        errors.append("No run mode is true in [mode].")

    if globals().get('early_stop', False) is True:
        tol = globals().get('early_stop_tol')
        if tol is None or tol <= 0:
            errors.append("early_stop = true requires early_stop_tol > 0 in [calibration].")

    if len(Man_n_vals) != len(Man_n_params):
        errors.append(
            f"Man_n_vals ({len(Man_n_vals)}) and Man_n_params "
            f"({len(Man_n_params)}) differ in length."
        )
    if len(bounds) != len(i0_guess):
        errors.append(
            f"bounds ({len(bounds)}) and i0_guess ({len(i0_guess)}) differ in length."
        )
    if adjust_n_rating:
        lens = {len(a), len(b), len(n_regions), len(function_type),
                len(max_n), len(min_n)}
        if len(lens) != 1:
            errors.append(
                "a, b, n_regions, function_type, max_n and min_n must be "
                "the same length."
            )
        if any(lo > hi for lo, hi in zip(min_n, max_n)):
            errors.append("min_n is larger than max_n for at least one region.")
    if algorythm.lower() not in ("nelder-mead", "sce-ua"):
        errors.append(f"Unknown algorythm: {algorythm}")
    if export_geojsons and not export_shapefile:
        errors.append("export_geojsons requires export_shapefile = true.")
    if structures is False and independent_structures:
        errors.append("independent_structures requires structures = true.")

    if errors:
        raise SystemExit("Config errors:\n  - " + "\n  - ".join(errors))


