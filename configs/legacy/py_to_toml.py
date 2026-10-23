"""Convert legacy Q2Dpy config.py files into TOML site configs (fixed template format).

Layout:
    OLD_ROOT/<site folder>/<config>.py
Output:
    OUT_DIR/<site folder lowercase>_<file stem>.toml
"""
import json
import re
import runpy
from pathlib import Path

# ============================== EDIT THESE ====================================
OLD_ROOT = Path(r"C:\Users\CND367\Documents\Python_Scripts\Q2Dpy\Site_Configs")
OUT_DIR = Path(r"C:\Users\CND367\Documents\Python_Scripts\Q2Dpy\Configs\legacy")
OVERWRITE = True
# ==============================================================================

TEMPLATE = r"""# HEC-RAS calibration site config: Elk Cr nr Haystack Butte
# Paths in single quotes are literal strings, backslashes and spaces are fine.

hec_version = "701"
EPSG = "EPSG:6514"           # EPSG:6514 NAD83(2011) MT state plane; EPSG:5703 NAVD88 height (m), use geoid2018
gauge_el_NAVD88m = 1348.689

# ---------------------------------------------------------------- run mode
[mode]
cal_observed = true
cal_indirect = false
cal_EG_slope = false
gen_ratecurv = false
sim_event    = false

# ------------------------------------------------------------- calibration
[calibration]
batch_process      = false         # calibrate list of given discharges
create_i0_simplex  = true          # only works with Nelder-Mead
algorythm          = "Nelder-Mead" # "Nelder-Mead" | "SCE-UA"
objective_function = "RMSE"        # "RMSE" | "MAE"
max_runs           = 300

structures             = false     # assign channel n to structures in cal_observed (currently assigns channel n to structure)
independent_structures = false     # calibrate structures separately from channel; input to simplex same as Q (structures must be true)

set_friction_slope = false         # override friction slopes prior to initial run
FS_params = ["us_fs", "ds_fs"]     # one or both for cal_EG_slope; us_fs must be first if both
upstream_friction_slope   = 0.003
downstream_friction_slope = 0.0025

Man_n_params = ["us_channel", "ds_channel"]   # e.g. Grassland, Road, NoData, Channel, Riparian
Man_n_vals   = [0.035, 0.0335]

Q_params     = ["upstream_BC"]     # discharge is last in bounds / initial guess
Q_params_cfs = 1000

# order: (us_fs, ds_fs, landcover_regions, structures, discharge)
bounds   = [[0.01, 0.12], [0.01, 0.12]]
i0_guess = [[0.03, 0.05], [0.03, 0.05]]

# --------------------------------------------------------------- options
[options]
find_cell_index  = false           # get cell index from WSP coordinates and update csv; must have unique id in ID field
get_inst_q       = false           # grab current reporting discharge for gauge; grabs MaxQ if false
export_shapefile = false           # gen_ratecurv & sim_event: save last inundation shapefile
export_geojsons  = false           # gen_ratecurv & sim_event: save all GeoJSONs (export_shapefile must be true)
verbose = true

# ------------------------------------------------------------------- paths
[paths]
directory = 'C:\Users\CND367\Documents\Python_Scripts\Q2Dpy\test_data'
# RAS_files, GIS, GIS/GeoJSONs, Input, Output are derived from `directory`

# ------------------------------------------------------------ RAS project
[ras]
prj  = "elk_cr_agusta"
geom = "g03"
flow = "u04"
plan = "p03"
landcover = 'Land Classification\LandCover.hdf'   # relative to RAS_files

[inputs]
grid_filename  = "2d_mesh.shp"            # GIS/   - for finding cell only
terrain_raster = "Terrain.tif"            # GIS/   - template for exporting WSEs
wse_filename   = "batch_channel_cal.csv"  # Input/
trendline      = "trendline.csv"          # Input/
q_list         = "Q_list.csv"             # Input/

[outputs]
simplex_filename      = "simplex_dataframe.csv"
iterations_filename   = "model_iterations.csv"
wse_prof_filename     = "wse_profiles_output.csv"
rating_curve_filename = "rating_curve.csv"
batch_filename        = "batch_results.csv"

# --------------------------------------------------- gen_ratecurv settings
[ratecurve]
use_Q_list      = true             # use csv list of discharges from Input instead of generating its own
min_cfs         = 0
max_cfs         = 420              # also used for sim_event
q_divisions     = 60               # number of runs; 1 = single event based on q
adjust_n_rating = true             # adjust n by discharge using a, b and trend params (log recommended)
n_regions       = ["us_channel", "ds_channel"]
function_type   = ["log", "log"]   # linear, log, exp, power, hyper (x is metric)
a     = [-0.00636011, -0.00636011]
b     = [0.06013817, 0.06013817]
max_n = [0.14, 0.14]
min_n = [0.025, 0.025]

# ------------------------------------------------------ sim_event settings
[sim_event]
hydrograph_ramp = false            # true: ramp q up, hold last hour at max; false: constant q
change_sim_time = false            # change sim time based on 15 min increments
sim_time_hr     = 3                # min 1 hr
set_datetime    = false            # true enables the settings below
start_date = "07JUN2023"
start_time = "00:00"
end_date   = "07JUN2023"
end_time   = "03:00"
computation_interval = "0.5SEC"

# ------------------------------------------------------- labeling bugfix
[labels]
perimeter = "Perimeter"
us_bc = "UpstreamBC"
ds_bc = "DownstreamBC"
"""

MISSING = object()

# keys read straight from the old config namespace, by section
DIRECT = {
    None: ["hec_version", "EPSG", "gauge_el_NAVD88m"],
    "mode": ["cal_observed", "cal_indirect", "cal_EG_slope", "gen_ratecurv", "sim_event"],
    "calibration": [
        "batch_process", "create_i0_simplex", "algorythm", "objective_function",
        "max_runs", "structures", "independent_structures", "set_friction_slope",
        "FS_params", "upstream_friction_slope", "downstream_friction_slope",
        "Man_n_params", "Man_n_vals", "Q_params", "Q_params_cfs", "bounds", "i0_guess",
    ],
    "options": ["find_cell_index", "get_inst_q", "export_shapefile", "export_geojsons", "verbose"],
    "ratecurve": [
        "use_Q_list", "min_cfs", "max_cfs", "q_divisions", "adjust_n_rating",
        "n_regions", "function_type", "a", "b", "max_n", "min_n",
    ],
    "sim_event": [
        "hydrograph_ramp", "change_sim_time", "sim_time_hr", "set_datetime",
        "start_date", "start_time", "end_date", "end_time", "computation_interval",
    ],
    "labels": ["perimeter", "us_bc", "ds_bc"],
}
INPUT_KEYS = ["grid_filename", "terrain_raster", "wse_filename", "trendline", "q_list"]
OUTPUT_KEYS = ["simplex_filename", "iterations_filename", "wse_prof_filename",
               "rating_curve_filename", "batch_filename"]


# ------------------------------------------------------------ value formatting
def fmt(v):
    if v is MISSING:
        return '""'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, Path):
        v = str(v)
    if isinstance(v, str):
        if "\\" in v and "'" not in v and "\n" not in v:
            return f"'{v}'"
        return json.dumps(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    return json.dumps(str(v))


# ----------------------------------------------------------- value collection
def ext_of(ns, key):
    v = ns.get(key)
    if v is None:
        return MISSING
    s = Path(str(v)).suffix.lstrip(".")
    return s or MISSING


def name_of(ns, key):
    v = ns.get(key)
    return Path(str(v)).name if v is not None else MISSING


def landcover_rel(ns):
    v = ns.get("lchdf_filename")
    if v is None:
        return MISSING
    v = Path(str(v))
    ras_dir = ns.get("ras_directory")
    if ras_dir is not None:
        try:
            return str(v.relative_to(Path(str(ras_dir))))
        except ValueError:
            pass
    return str(v)


def collect_values(ns):
    ns = dict(ns)
    fs = ns.get("friction_slope")
    if isinstance(fs, (list, tuple)) and len(fs) >= 2:
        ns.setdefault("upstream_friction_slope", fs[0])
        ns.setdefault("downstream_friction_slope", fs[-1])

    vals = {}
    for sec, keys in DIRECT.items():
        for k in keys:
            vals[(sec, k)] = ns.get(k, MISSING)

    d = ns.get("Directory")
    vals[("paths", "directory")] = str(d) if d is not None else MISSING
    vals[("ras", "prj")] = ns.get("prj", MISSING)
    vals[("ras", "geom")] = ext_of(ns, "geom_filename")
    vals[("ras", "flow")] = ext_of(ns, "flow_filename")
    vals[("ras", "plan")] = ext_of(ns, "plan_filename")
    vals[("ras", "landcover")] = landcover_rel(ns)
    for k in INPUT_KEYS:
        vals[("inputs", k)] = name_of(ns, k)
    for k in OUTPUT_KEYS:
        vals[("outputs", k)] = name_of(ns, k)
    return vals


# ----------------------------------------------------------------- rendering
LINE_RE = re.compile(
    r"^(?P<key>\w+)(?P<eq>\s*=\s*)(?P<val>.*?)(?:(?P<gap>\s+)(?P<comment>#.*))?$"
)
SECTION_RE = re.compile(r"^\[(\w+)\]\s*$")


def render(vals, site_name):
    out, missing, section = [], [], None
    for i, line in enumerate(TEMPLATE.splitlines()):
        if i == 0:
            out.append(f"# HEC-RAS calibration site config: {site_name}")
            continue
        s = SECTION_RE.match(line)
        if s:
            section = s.group(1)
            out.append(line)
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            out.append(line)
            continue
        m = LINE_RE.match(line)
        if not m or (section, m.group("key")) not in vals:
            out.append(line)
            continue

        key = m.group("key")
        value = vals[(section, key)]
        left = key + m.group("eq") + fmt(value)
        comment = m.group("comment")

        if value is MISSING:
            missing.append(f"{section + '.' if section else ''}{key}")
            comment = ("# MISSING in source; " + comment[1:].lstrip()) if comment \
                else "# MISSING in source config"

        if comment:
            orig_comment = m.group("comment")
            if orig_comment:
                orig_col = len(line) - len(orig_comment)  # column of '#' in template
                pad = max(1, orig_col - len(left))
            else:
                pad = 2  # template line had no comment; we only added the MISSING note
            out.append(left + " " * pad + comment)
        else:
            out.append(left)
    return "\n".join(out) + "\n", missing


# ----------------------------------------------------------------------- main
def safe_name(text):
    return re.sub(r"\s+", "_", text.strip().lower())


def looks_like_config(ns):
    return any(k in ns for k in ("hec_version", "prj", "Directory", "cal_observed"))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    converted, skipped = 0, []

    for site in sorted(p for p in OLD_ROOT.iterdir() if p.is_dir()):
        for py in sorted(site.glob("*.py")):
            label = f"{site.name}/{py.name}"
            try:
                ns = runpy.run_path(str(py))
            except Exception as exc:
                skipped.append((label, f"failed to run: {exc!r}"))
                continue
            if not looks_like_config(ns):
                skipped.append((label, "does not look like a config"))
                continue

            target = OUT_DIR / f"{safe_name(site.name)}_{py.stem}.toml"
            if target.exists() and not OVERWRITE:
                skipped.append((label, f"{target.name} already exists"))
                continue

            text, missing = render(collect_values(ns), site.name)
            target.write_text(text, encoding="utf-8")
            converted += 1
            note = f"\n     missing {len(missing)}: {', '.join(missing)}" if missing else ""
            print(f"OK   {label} -> {target.name}{note}")

    print(f"\nConverted {converted} file(s).")
    for label, why in skipped:
        print(f"SKIP {label}: {why}")


if __name__ == "__main__":
    main()