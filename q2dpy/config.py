"""Site config loader for Q2Dpy.

Reads a TOML site config and exposes its values as module-level names, so the
rest of the code can keep using `import config` and `config.<name>`.

"""
import shutil
import tomllib
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

_DEFAULTS = {"early_stop": False, "early_stop_tol": None}

_flat = dict(_DEFAULTS)
_flat.update({k: v for k, v in _raw.items() if not isinstance(v, dict)})
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
geojson_directory = gis_directory / "GeoJSONs"
input_directory = Directory / "Input"
output_directory = Directory / "Output"


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
simplex_filename = output_directory / _out["simplex_filename"]
iterations_filename = output_directory / _out["iterations_filename"]
wse_prof_filename = output_directory / _out["wse_prof_filename"]
rating_curve_filename = output_directory / _out["rating_curve_filename"]
batch_filename = output_directory / _out["batch_filename"]


# ------------------------------------------------------ derived discharge vals
Q_params_vals = [round(Q_params_cfs * CFS_TO_CMS, 3)]
min_q = round(min_cfs * CFS_TO_CMS, 3)
max_q = round(max_cfs * CFS_TO_CMS, 3)


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

    if early_stop and (early_stop_tol is None or early_stop_tol <= 0):
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


# -------------------------------------------------------------------- snapshot
def snapshot_config():
    """Copy the TOML into the Output folder so results record their settings."""
    output_directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_PATH, output_directory / CONFIG_PATH.name)


