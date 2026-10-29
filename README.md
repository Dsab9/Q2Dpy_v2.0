# Q2Dpy

Python automation for calibrating and running 2D HEC-RAS models. Q2Dpy edits a HEC-RAS project's input files, runs the plan through the HEC-RAS COM controller, reads the results from the plan HDF file, and repeats until a calibration converges or a set of discharges has been run. Every run gets its own dated Input and Output folder, and finished calibrations produce an HTML report.

It supports four workflows:

| Workflow | Config switch | What it does |
|---|---|---|
| Calibrate to observed discharge | `cal_observed` | Fixed discharge, solves for Manning's n (and optionally boundary friction slopes) to match surveyed water surface elevations |
| Indirect discharge | `cal_indirect` | Solves for Manning's n **and** discharge from high-water marks |
| Rating curve | `gen_ratecurv` | Runs a range or list of discharges and records stage vs. discharge at a gauge cell |
| Single event | `sim_event` | Runs one discharge (a set value or the current gauge reading) and optionally exports an inundation shapefile / GeoJSON |

> Windows only. HEC-RAS is driven through its COM controller (`pywin32`), and HEC-RAS must be installed on the same machine.

---

## Contents

1. [Requirements](#requirements)
2. [Building the environment](#building-the-environment)
3. [Project layout](#project-layout)
4. [Setting up a site](#setting-up-a-site)
5. [Configuration reference](#configuration-reference)
6. [Running Q2Dpy](#running-q2dpy)
7. [Run folders](#run-folders)
8. [Calibration reports](#calibration-reports)
9. [How each workflow works](#how-each-workflow-works)
10. [Input and output files](#input-and-output-files)
11. [Units and conventions](#units-and-conventions)
12. [Converting legacy configs](#converting-legacy-configs)
13. [Troubleshooting](#troubleshooting)
14. [Development notes](#development-notes)

---

## Requirements

- Windows 10/11
- HEC-RAS installed (developed against 6.6 and 7.0.1). The COM controller must be registered. The ProgID is `RAS<version>.HECRASController`, for example `RAS701.HECRASController`.
- Python 3.11 or newer (the config loader uses `tomllib`)
- SciPy 1.11 or newer (early stopping uses the `intermediate_result` callback interface)
- A 2D HEC-RAS unsteady-flow project with a land-cover HDF (`Land Classification\LandCover.hdf`) and a mesh shapefile exported from RAS Mapper
- Optional: network access to the AQUARIUS server, only for `get_inst_q = true`

---

## Building the environment

The geospatial packages (GDAL, rasterio, geopandas) are painful to install with `pip` on Windows, so a conda environment is recommended.

### Option A: conda (recommended)

```bat
conda create -n q2dpy python=3.12
conda activate q2dpy
conda install -c conda-forge numpy pandas "scipy>=1.11" h5py shapely geopandas rasterio gdal matplotlib requests
pip install pywin32 sambo
```

Or use an `environment.yml`:

```yaml
name: q2dpy
channels:
  - conda-forge
dependencies:
  - python=3.12
  - numpy
  - pandas
  - scipy>=1.11
  - h5py
  - shapely
  - geopandas
  - rasterio
  - gdal
  - matplotlib
  - requests
  - pip
  - pip:
      - pywin32
      - sambo
```

```bat
conda env create -f environment.yml
conda activate q2dpy
```

### Option B: venv + pip

Only if you already have working wheels for GDAL and rasterio:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install numpy pandas "scipy>=1.11" h5py shapely geopandas rasterio matplotlib requests pywin32 sambo
pip install GDAL    # needs a wheel matching your Python and GDAL install
```

### Package purposes

| Package | Used for |
|---|---|
| `pywin32` | COM link to HEC-RAS (`win32com.client`) |
| `h5py` | Reading and editing HEC-RAS HDF files (results, land cover, geometry); reading plan metadata for reports |
| `numpy`, `pandas`, `scipy` | Data handling and Nelder-Mead optimization |
| `sambo` | SCE-UA optimizer (optional algorithm) |
| `geopandas`, `shapely`, `rasterio`, `gdal` | Mesh cell lookup and inundation shapefile export |
| `requests` | AQUARIUS discharge download |
| `matplotlib` | Report figures and trend-line plots |

The calibration report is a self-contained HTML page built with matplotlib and pandas. It no longer needs Jupyter, `nbformat`, `plotly` or `itables`.

### Check the install

```bat
python -c "import numpy, pandas, scipy, h5py, geopandas, rasterio, shapely, sambo, matplotlib, win32com.client; from osgeo import gdal; print('imports ok')"
python -c "import tomllib, scipy; print('tomllib ok, scipy', scipy.__version__)"
```

To confirm the HEC-RAS controller is registered (this launches HEC-RAS in the background; close it afterward):

```bat
python -c "import win32com.client as w; h=w.Dispatch('RAS701.HECRASController'); print(h.HECRASVersion()); h.QuitRas()"
```

Match the `701` to the version you installed. To list registered ProgIDs:

```bat
reg query HKCR /f HECRASController /k
```

Make sure Python and HEC-RAS have the same bitness. A 32-bit Python cannot attach to a 64-bit-only controller.

---

## Project layout

```
Q2Dpy_v2.0/
  q2dpy/                  code (run everything from this folder)
    main.py               entry point and workflow selection
    config.py             loads one site TOML, creates run folders, validates settings
    calibration.py        observation loading, objective function, optimizers, simplex, early stopping
    rating_curve.py       rating-curve generation and single-event runs
    grid.py               maps survey points to 2D mesh cells
    csv_log.py            helpers that append rows to the result CSVs
    units.py              unit conversions (cfs, m3/s, ft, m)
    model.py              HecRas class: edits RAS files, runs the plan, reads results
    openRAS.py            HEC-RAS launch helper
    rasfileparser.py      reads and edits RAS flow (.u##) and plan (.p##) text files
    objectivefun.py       RMSE / MAE
    n_adjuster.py         discharge-dependent Manning's n trend functions
    shape_export.py       inundation shapefile and GeoJSON export
    aquarius.py           current discharge from AQUARIUS (optional)
    plot_trend.py         fits and plots Q vs n trend lines
    stats.py              statistics for indirect-discharge results
    reporting/            calibration report package
      __init__.py         exports make_report
      __main__.py         command line entry: python -m reporting <output folder>
      builder.py          report classes (observed / indirect) and HTML assembly
      data.py             loading run files and the analysis (best run, tolerance, residuals)
      plots.py            matplotlib figures
      run_report.py       optional script: edit a path and build a report
  configs/
    template.toml         example site config
    legacy/               older configs and the legacy converter
  test_data/              example HEC-RAS project for smoke tests
  reporting/              generated reports, one folder per run (created on first report)
```

---

## Setting up a site

Q2Dpy reads and **overwrites** files inside your HEC-RAS project (flow file, land-cover HDF, plan file, and geometry file). **Working on a copy of HEC-RAS files is recommended.**

Expected data folder:

```
<site directory>/
  RAS_files/              HEC-RAS project (.prj, .g##, .u##, .p##, .hdf, Land Classification\)
  GIS/                    2D mesh shapefile, terrain raster
  Input/                  observation CSV, Q list, trend line CSV; per-run snapshot folders are added here
  Output/                 created automatically; one subfolder per run
```

Checklist before the first run:

1. The plan runs cleanly in the HEC-RAS GUI, with no mesh errors, and its geometry and unsteady flow file are assigned. MODEL MUST BE RUN AT LEAST ONCE MANUALLY AND HEC-RAS CLOSED PRIOR TO AUTOMATION!
2. The unsteady flow file has an upstream hydrograph boundary and a downstream normal depth (friction slope) boundary. Their names must match `us_bc` and `ds_bc` in the config.
3. Manning's n calibration regions exist in the land-cover HDF, and their names match `Man_n_params`.
4. The mesh shapefile (exported from RAS Mapper with a `CellIndex` field) is in `GIS/`.
5. The observation CSV is in `Input/` (see [Input and output files](#input-and-output-files)).
6. The model's preprocessed files are current. If the geometry changed, open it in the GUI and recompute once.

---

## Configuration reference

Each site or run is one TOML file in `configs/`. To select it, edit this line at the top of `q2dpy/config.py`:

```python
CONFIG_NAME = "template.toml"
```

The loader puts every key from the top level and from the sections `[mode]`, `[calibration]`, `[options]`, `[ratecurve]`, `[sim_event]` and `[labels]` into the `config` module, so the rest of the code reads `config.<key>`. Paths are built from the `directory` and the file names in the TOML. Single-quoted TOML strings are literal, so Windows backslashes and spaces are safe. Keys in `[paths]`, `[ras]`, `[inputs]` and `[outputs]` are **not** copied directly; `config.py` uses them to build the derived paths. The `[report]` section is read by the reporting package from the run's saved copy of the TOML, not by `config.py`.

Optional keys have defaults in `reporting/data.py` or are checked in `config.validate()`, so older configs that lack them still load. `early_stop` defaults to off, and `[report]` can be left out entirely.

### Top level

| Key | Meaning |
|---|---|
| `hec_version` | Controller version suffix, e.g. `"701"` gives `RAS701.HECRASController` |
| `EPSG` | Coordinate reference system for exports, e.g. `"EPSG:6514"` (NAD83(2011) Montana state plane) |
| `gauge_el_NAVD88m` | Gauge orifice elevation (m, NAVD88). Stage is computed as WSE minus this value |

### `[mode]` (set one to `true`)

`cal_observed`, `cal_indirect`, `cal_EG_slope`, `gen_ratecurv`, `sim_event`

`cal_EG_slope` can be combined with `cal_observed` or `cal_indirect` to also calibrate the boundary friction slopes.

### `[calibration]`

| Key | Meaning |
|---|---|
| `batch_process` | Calibrate each row of the observation file (each with its own discharge) |
| `create_i0_simplex` | Build the starting simplex from `i0_guess` (Nelder-Mead only) |
| `algorythm` | `"Nelder-Mead"` or `"SCE-UA"` (spelling matches the code) |
| `objective_function` | `"RMSE"` or `"MAE"` |
| `max_runs` | Maximum optimizer iterations |
| `early_stop` | `true` ends the optimization once the objective values flatten out (optional, default `false`) |
| `early_stop_tol` | Standard deviation of the last 2(n+1) objective values below which the run stops. Same units as the objective (m for RMSE). Required when `early_stop = true`; 1e-4 is a good starting point |
| `structures`, `independent_structures` | Assign the channel n to bridges / culverts; `independent_structures` calibrates a separate structure n (requires `structures`) |
| `set_friction_slope`, `upstream_friction_slope`, `downstream_friction_slope` | Override boundary friction slopes before the first run |
| `FS_params` | `["us_fs", "ds_fs"]`; either or both when `cal_EG_slope` is on. `us_fs` must come first |
| `Man_n_params`, `Man_n_vals` | Land-cover region names to calibrate and their starting n values |
| `Q_params`, `Q_params_cfs` | Name of the discharge parameter in the log, and the starting / fixed discharge in cfs |
| `bounds`, `i0_guess` | Lower/upper bound and initial-simplex range per parameter |

**Parameter order for `bounds` and `i0_guess`:** friction slopes (if used), then Manning's n regions (then the structure n if independent), then discharge last for `cal_indirect`. The number of rows must equal the number of calibrated parameters. The report uses the same order to attach bounds to each parameter, so a wrong count means no bounds in the report.

### `[options]`

| Key | Meaning |
|---|---|
| `find_cell_index` | Look up the mesh cell for each Easting/Northing in the observation file and write `Cell_Index` back to it. Requires a unique `ID` column |
| `get_inst_q` | `sim_event` only: use the current AQUARIUS discharge instead of `max_cfs` |
| `export_shapefile`, `export_geojsons` | For `gen_ratecurv` and `sim_event`: save the last inundation shapefile, and optionally a GeoJSON per run (needs `export_shapefile`) |
| `verbose` | Extra progress printing |

### `[paths]`, `[ras]`, `[inputs]`, `[outputs]`

| Section | Keys |
|---|---|
| `[paths]` | `directory`, the site root. `RAS_files`, `GIS`, `Input`, `Output` are derived from it |
| `[ras]` | `prj` (project name), `geom`, `flow`, `plan` (file extensions such as `g03`, `u04`, `p03`), `landcover` (path relative to `RAS_files`) |
| `[inputs]` | `grid_filename` and `terrain_raster` (in `GIS/`); `wse_filename`, `trendline`, `q_list` (in `Input/`) |
| `[outputs]` | `simplex_filename`, `iterations_filename`, `wse_prof_filename`, `rating_curve_filename`, `batch_filename` (written inside the run's Output subfolder) |

### `[ratecurve]`

| Key | Meaning |
|---|---|
| `use_Q_list` | Use `Input/Q_list.csv` instead of generating evenly spaced discharges |
| `min_cfs`, `max_cfs` | Discharge range (`max_cfs` is also used by `sim_event`) |
| `q_divisions` | Number of runs across the range |
| `adjust_n_rating` | Change Manning's n with discharge, using a trend line |
| `n_regions`, `function_type`, `a`, `b`, `min_n`, `max_n` | Per-region trend: `linear`, `log`, `exp`, `power` or `hyper`, with coefficients and clamps. For `log`, n = a * ln(Q) + b with Q in m3/s |

### `[sim_event]`

`hydrograph_ramp`, `change_sim_time`, `sim_time_hr`, `set_datetime`, `start_date`, `start_time`, `end_date`, `end_time`, `computation_interval`. These control the hydrograph written into the flow file and the simulation window in the plan file.

### `[report]`

| Key | Meaning |
|---|---|
| `report_tol_m` | Acceptance tolerance in meters. A run counts as acceptable if its objective is within this distance of the best run. If the section is missing, the report uses 10% of the best objective and says so in its summary |

### `[labels]`

`perimeter` (2D flow area name), `us_bc`, `ds_bc` (boundary condition names). These must match the names inside the HEC-RAS geometry HDF files.

### Calculated values

These are computed by `config.py`: `Q_params_vals`, `min_q`, `max_q` (m3/s from the cfs values, using the constant in `units.py`), `friction_slope` (upstream and downstream combined), the run folder paths, and every output file path.

---

## Running Q2Dpy

1. Activate the environment: `conda activate q2dpy`
2. Set `CONFIG_NAME` in `q2dpy/config.py` to the TOML you want.
3. Close HEC-RAS if it is open.
4. From the `q2dpy` code folder:

```bat
python main.py
```

On start-up, `config.validate()` checks that the project files exist, that a run mode is selected, that lists have matching lengths, that `early_stop_tol` is set when `early_stop` is on, and a few option dependencies (for example `export_geojsons` needs `export_shapefile`). Then `config.start_run()` creates the run folders, and `config.snapshot_inputs()` copies the config and input files into the run's Input folder, so every result set records the settings and data that produced it.

HEC-RAS opens on screen for each model run, then closes. Do not use the computer's HEC-RAS windows while a calibration is running.

**Smoke test:** set `max_runs = 5` on a copy of your config and run it. Check `Output/<run>/model_iterations.csv` for the rows before starting a full run (about 300 model runs is typical).

---

## Run folders

Each run creates a pair of folders with the same name, `<YYYYMMDD>_<mode>`, for example `20261029_cal_observed`. If the name already exists, `_1`, `_2` and so on are appended, so nothing is overwritten.

| Mode part of the name | When |
|---|---|
| `cal_observed`, `cal_indirect`, `gen_ratecurv`, `sim_event`, `cal_EG_slope` | The selected `[mode]` switch |
| `_EG` suffix | `cal_EG_slope` combined with another calibration mode |
| `_batch` suffix | Calibration with `batch_process = true` |

```
<site directory>/
  Input/
    batch_channel_cal.csv       the working input files
    20261029_cal_observed/      snapshot: the config TOML and every file that was in Input/ at the start
  Output/
    20261029_cal_observed/      model_iterations.csv, wse_profiles_output.csv, GeoJSONs\, ...
```

The snapshot is taken after the cell-index step, so the copied observation CSV is the one the run actually used. Reports read the snapshot to find the settings, which is why a report can be built later without the original config.

---

## Calibration reports

When a `cal_observed`, `cal_indirect` or `cal_EG_slope` run finishes (and `batch_process` is off), `main.py` builds a report automatically. If the report fails, the results are still saved and the console prints the command to rerun it.

Reports are written to `reporting/<project>_<run name>` in the repository root. Rerunning for the same run creates `_1`, `_2` and so on.

| Item | Contents |
|---|---|
| `report.html` | One self-contained page with the figures embedded |
| `figures/` | PNG files for each plot |
| `tables/` | CSV files: parameter ranges, acceptable runs, ten best runs, residuals, worst points |

### What the report shows

- **Summary:** run, project, mode, algorithm, objective function, number of model runs, best objective and iteration, tolerance and where it came from, number of acceptable runs, and bias, MAE and maximum error at the observation points.
- **Stopping:** whether early stopping ended the run, and the final `Obj_Std`.
- **Warnings:** a best value within 5% of a bound (the true value may lie outside the search range) and fewer than five acceptable runs (the ranges are a lower bound).
- **Calibrated parameters:** best value, acceptable range and bounds for each parameter that changed during the run.
- **Figures:** convergence, parameters vs iteration, objective vs parameter, water surface profile, and residuals along the reach.
- **Indirect runs only:** a discharge result table (best, acceptable low and high, in m3/s and cfs) and a discharge-vs-roughness plot.
- **Context:** HEC-RAS plan metadata and the calibration settings.

### Acceptable range

A run is acceptable if its objective is within the tolerance of the best run. The acceptable range of a parameter is the minimum and maximum of that parameter among the acceptable runs. It only reflects the values the optimizer tried, so treat it as a lower bound on the true uncertainty. For `cal_observed` it also assumes the fixed discharge is correct.

Set the tolerance in `[report] report_tol_m` based on the accuracy of your surveyed marks, or override it for one report with `--tol`.

### Running a report without the model

```bat
cd q2dpy
conda activate q2dpy
python -m reporting ..\test_data\Output\20261029_cal_observed
python -m reporting <output folder> --tol 0.05
```

| Option | Meaning |
|---|---|
| `--tol` | Tolerance in meters for this report (overrides `report_tol_m`) |
| `--input-dir` | Snapshot folder, if it is not the sibling `Input/<run name>` |
| `--config` | TOML name inside the snapshot folder, if there are several |
| `--report-root` | Folder that receives report folders (default `reporting/` in the repository root) |

From Python:

```python
from reporting import make_report
make_report(r"C:\...\Output\20261029_cal_observed", tol_m=0.05).run()
```

`reporting/run_report.py` is a script version: edit `OUTPUT_DIR` and `TOL_M` at the top and run it as a module from the `q2dpy` folder with `python -m reporting.run_report`. Running the file directly will fail on the import because the package folder, not `q2dpy`, ends up on the search path.

A report needs `model_iterations.csv` and `wse_profiles_output.csv` in the Output run folder and the config TOML in the matching Input run folder. It does not import `config.py`.

---

## How each workflow works

### Common loop (calibration)

1. `main.py` validates the config, creates the run folders, optionally finds mesh cells, takes the input snapshot, loads the observations (`load_obs_df`), and applies one-time edits (simulation date/time, friction slopes, starting discharge). It then changes the working directory to the run's Output folder.
2. `create_i0_simplex` builds the starting Nelder-Mead simplex: all lower bounds, random points within each range, and all upper bounds.
3. `optimize_model` assembles the starting vector from the config and hands `calc_obj_function` to SciPy's Nelder-Mead or to `sambo`'s SCE-UA.
4. Each time the optimizer asks for an objective value, `calc_obj_function`:
   - rounds the trial parameters to 6 decimals;
   - writes them into the model (`apply_trial_parameters`): friction slopes into the flow file, Manning's n into the land-cover HDF (and bridge n into the geometry), discharge into the flow file;
   - runs the plan through the COM controller and reads the last time step's water surface for every cell (`run_and_read_wse`; it waits 4 s afterward because results are not ready immediately);
   - compares modeled and observed WSE at the survey cells (`score_model`) and returns RMSE or MAE;
   - records the standard deviation of the recent objective values (see Early stopping);
   - appends the run to `model_iterations.csv` (`log_iteration`) and adds that run's WSE profile to `wse_profiles_output.csv` (`log_wse_profile`).
5. When it finishes, the report is built (see [Calibration reports](#calibration-reports)).

### Early stopping

Nelder-Mead can settle on a plateau where the RMSE barely changes, then keep drifting toward a different region of parameter space that fits no better. Early stopping ends the run when the objective has flattened out.

- A `ConvergenceTracker` (in `calibration.py`) keeps the last 2 x (n + 1) objective values, which is two simplexes' worth for n calibrated parameters. Example: 3 parameters give a window of 8 values.
- After every model run it computes the standard deviation of that window and writes it to the `Obj_Std` column of `model_iterations.csv`. This happens whether or not early stopping is on, so you can pick a tolerance from a normal run. The column is empty until the window fills.
- If `early_stop = true`, the optimizer callback stops the run at the end of the iteration in which the standard deviation falls below `early_stop_tol`. SciPy returns normally with its best result; for SCE-UA the same callback is passed to `sambo`.
- Each call to `optimize_model` creates a new tracker, so every row of a batch calibration starts fresh.
- The model files on disk hold the last trial parameters, not necessarily the best. The best run is the row with the lowest `Obj_Func_Value` in `model_iterations.csv`, and the report identifies it.

**Choosing the tolerance:** run once with `early_stop = false`, look at the convergence figure in the report (or plot `Obj_Std` and `Obj_Func_Value` against `iteration`), and set `early_stop_tol` just above the standard deviation on the plateau and below the values during real convergence. 1e-4 has worked well as a starting point.

Early stopping accepts the first flat region the optimizer finds, which depends on the starting simplex. If different starts give different n values at the same RMSE, the problem is not well constrained (equifinality); tighter `bounds`, a better `i0_guess` or more observations will help more than a different tolerance. The "Objective vs parameter" figure and the acceptable ranges in the report show this directly.

### `cal_observed`

The discharge is fixed (`Q_params_cfs`). The optimizer varies Manning's n (and friction slopes if `cal_EG_slope`).

### `cal_indirect`

Discharge is one of the parameters, placed last. Use it when only high-water marks are known. The report gives the best discharge and the range among acceptable runs. `stats.py` summarizes the final simplex (mean Q, standard deviation, confidence intervals).

### Batch calibration

With `batch_process = true`, each row of the observation file is calibrated on its own, using that row's `Q(cfs)`. The last iteration of each row is appended to `batch_results.csv`. Batch mode currently supports `cal_observed` only, and no report is generated.

### Rating curve

For each discharge (from `Q_list.csv`, or `q_divisions` steps between `min_cfs` and `max_cfs`), Q2Dpy sets the flow, optionally sets the discharge-dependent Manning's n, runs the plan, and appends a row to `rating_curve.csv`: orifice elevation, WSE, stage in m and ft, discharge in m3/s and cfs, and the n values used. Inundation shapefiles / GeoJSONs can be exported per run.

To build the n-versus-Q trend, put calibrated results in `Input/trendline.csv` and use `plot_trend.py` to fit the `a` and `b` coefficients for each function type.

### Single event

`sim_event` runs one discharge, either `max_cfs` or the current reading from AQUARIUS, and optionally exports the inundation extent.

### Inundation export

`shape_export.export_shapefile` joins each cell's final WSE to the mesh shapefile, rasterizes it on the terrain raster grid, subtracts the terrain, keeps depths above 0.01 m, vectorizes the result, drops polygons of 3 m2 or less, and writes the inundation shapefile into the run's Output folder. `saveas_geojson` reprojects it to EPSG:4326 and names the file by stage in feet.

---

## Input and output files

### Observation CSV (`Input/<wse_filename>`)

| Column | Needed for |
|---|---|
| `ID` | Unique id per point (normal calibration; also `find_cell_index`) |
| `Easting`, `Northing` | `find_cell_index` (in the same CRS as the mesh shapefile) |
| `Cell_Index` | All modes. Written by `find_cell_index` or supplied by you |
| `Channel_Distance` | Normal calibration (used for profile plots and the report) |
| `Elev_m` | Calibration: observed water surface elevation (m, NAVD88) |
| `Q(cfs)` | Batch mode: discharge for that row |

`load_obs_df()` checks the columns required by the current mode and stops with a clear message before any model run if some are missing.

### Other inputs

- `Input/Q_list.csv`: a `Q(cfs)` column of discharges for the rating curve
- `Input/trendline.csv`: x and y columns for `plot_trend.py` (the first row holds the axis titles)
- `GIS/<terrain_raster>`: terrain GeoTIFF used as the template for inundation export
- `GIS/<grid_filename>`: the 2D mesh cell shapefile

### Outputs (`Output/<run name>/`)

| File | Contents |
|---|---|
| `model_iterations.csv` | One row per model run: parameter values, discharge, friction slopes, `iteration`, `Obj_Func_Value`, `Obj_Std` (std of the last two simplexes' objective values) |
| `wse_profiles_output.csv` | Observation points with a column `I<n>` of modeled WSE for each iteration |
| `batch_results.csv` | Final iteration of each batch row |
| `rating_curve.csv` | Stage-discharge results |
| `inundation.shp`, `GeoJSONs/*.geojson` | Inundation extent exports |

### Run snapshot (`Input/<run name>/`)

The config TOML and a copy of every file that was in `Input/` when the run started.

### Reports (`reporting/<project>_<run name>/`)

`report.html`, `figures/*.png`, `tables/*.csv`. See [Calibration reports](#calibration-reports).

---

## Units and conventions

- HEC-RAS values and internal calculations are SI: discharge in m3/s, elevations in m.
- Config inputs and some output columns use cfs and feet (`Q_params_cfs`, `min_cfs`, `max_cfs`, `Q(cfs)`, `stage(ft)`).
- All conversions go through `units.py` (`cfs_to_cms`, `cms_to_cfs`, `m_to_ft`, `ft_to_m`). The constants used are 1 cfs = 0.02832 m3/s and 1 ft = 0.3048 m. `config.py` takes its cfs-to-m3/s factor from `units.py`.
- `aquarius.py` still hard-codes the rounded factor `0.02832` for the AQUARIUS conversion.
- Report tolerances and fit statistics are in meters.
- Manning's n calibration region names are stored as bytes in the HDF files. `string_to_binary` and `binary_to_string` in `model.py` convert between the two.

---

## Converting legacy configs

Older runs used a Python `config.py`. `py_to_toml.py` (in `configs/legacy`) converts a tree of those files to the TOML format:

```
legacy/<site folder>/<any config>.py   ->   configs/<site folder, lowercase>_<file name>.toml
```

Set `OLD_ROOT` and `OUT_DIR` at the top of the script and run it. Notes:

- It **executes** each old file, so only run it on code you trust.
- Fields missing from an old config are written as `""` with a `# MISSING in source config` comment, because TOML has no null. Fix these by hand. An empty string is falsy, so a missing flag behaves as `false`, but a missing number will fail when it is used.
- Converted files do not include `early_stop`, `early_stop_tol` or `[report]`. Add them by hand if you want early stopping or a specific report tolerance; without them early stopping stays off and the report uses its 10% fallback.
- Spaces in folder names become underscores in the output file name.
- It prints a report of the missing fields for every file.

---

## Troubleshooting

**`Compute_CurrentPlan` returns `False`**
Look at the returned messages. "Computations were not performed, there must have been some missing data in the input files" means HEC-RAS itself rejected the plan. Check that the plan has geometry and an unsteady flow file assigned, that every boundary condition has data, and that the plan runs in the GUI.

**False mesh errors after moving a project from HEC-RAS 6.6 to 7.0.x**
A model saved in 6.6 can fail mesh validation in 7.0.1 even though the mesh is fine. Open the project in the new version, run Compute Cell Properties in RAS Mapper, save the geometry, and run the plan once in the GUI. If that is not enough, delete the stale geometry preprocessor (`.c##`) and the plan HDF output (with a backup first) and recompute. Check the HEC-RAS release notes for fixes in later 7.0.x versions.

**`OMP: Warning #182: OMP_PLACES: ignored because KMP_AFFINITY has been defined`**
Harmless warning from the OpenMP runtime used by the 2D solver. It means two thread-affinity variables are defined. Remove one of `OMP_PLACES` or `KMP_AFFINITY` from the environment if you want it gone.

**HEC-RAS opens, but the plan never starts or closes after a few seconds**
Confirm `hec_version` matches the installed ProgID exactly, that Python and HEC-RAS have the same bitness, and that no other HEC-RAS window is open. The controller should be dispatched once and `QuitRas()` called only after computation finishes.

**`Config file not found`**
`config.py` looks for `CONFIG_NAME` in the `configs` folder next to the code folder. Check the spelling and the folder location.

**`NameError` for a config key**
The key is missing from the TOML, or it is in a section that is not flattened (`[paths]`, `[ras]`, `[inputs]` and `[outputs]` are not). Compare your file with `configs/template.toml`.

**`Config errors: early_stop = true requires early_stop_tol > 0`**
Add `early_stop_tol` to `[calibration]`.

**Early stopping never triggers, or triggers too early**
Open `model_iterations.csv` (or the convergence figure in the report) and look at `Obj_Std`. If it never drops below `early_stop_tol`, the tolerance is too strict for that site. If it drops below the tolerance during the initial convergence, it is too loose. Remember `Obj_Std` is empty until the window of 2 x (n + 1) runs is full, and the run only stops at the end of an iteration.

**`TypeError` / odd behavior with the optimizer callback**
Early stopping needs SciPy 1.11 or newer. Check with `python -c "import scipy; print(scipy.__version__)"`.

**`ValueError: ... is missing required column(s)`**
The observation CSV is missing a column the current mode needs. Run with `find_cell_index = true` to create `Cell_Index`, or add the column.

**Results read as stale or empty after a run**
The plan HDF takes a moment to finish writing. `run_and_read_wse` waits 4 seconds after the run. Do not remove that wait unless you have tested the replacement on your machine.

**`Report failed (...)` at the end of a run**
The results are already saved. Fix the cause shown in the message and rerun with `python -m reporting <output folder>` from the `q2dpy` folder.

**`Report not created: Input snapshot folder not found`**
The report looks for `Input/<run name>` next to the `Output` folder. Pass `--input-dir` if you moved it.

**`Several .toml files in ...`**
More than one TOML is in the snapshot folder. Pass `--config <name>.toml`.

**`NotImplementedError` from a report**
Reports exist for calibration runs only (`cal_observed`, `cal_indirect`, `cal_EG_slope`), and not for batch calibrations.

**`ModuleNotFoundError: reporting` when running `run_report.py`**
Run it as a module from the `q2dpy` folder (`python -m reporting.run_report`), or move it up next to `main.py`.

**`ModuleNotFoundError` / `ImportError` (other modules)**
Run commands from the `q2dpy` folder with the environment active. Modules inside `reporting/` import each other with relative imports (`from . import data`), and the package imports top-level modules such as `units` from the `q2dpy` folder.

---

## Development notes

- **Credentials.** `aquarius.py` currently keeps the server name and login in the source file. Move the credentials to environment variables or a local file that is not committed, and do not push them to a shared repository.
- **Globals.** Observation data are passed into the calibration functions as arguments (`obs_df`, `batch_row`). Do not reintroduce module-level DataFrames.
- **Adding a config key.** Add it to the TOML (in the section that fits), then read it as `config.<key>`. Keys must be unique across sections because the sections are flattened into one namespace. If you add a new section that holds settings, add its name to `_FLAT_SECTIONS` in `config.py`, and to `FLAT_SECTIONS` in `reporting/data.py` if reports need it. Add a check to `validate()` if the key has dependencies.
- **Run folders.** All output paths come from `config._build_output_paths`. Code should read `config.output_directory` and the `*_filename` names after `start_run()` has been called, never build paths from the Output root.
- **Model handle.** Use `HecRas.from_config()` to create a model handle. It only stores file paths, so creating one per run is cheap.
- **Objective function structure.** `calc_obj_function` in `calibration.py` is a coordinator over small functions: `apply_trial_parameters`, `run_and_read_wse`, `collect_param_row`, `score_model`, `log_iteration` and `log_wse_profile`. Change behavior in the small function, not in the coordinator.
- **Reporting structure.** `data.py` loads files and does the analysis with no plotting and no dependency on `config.py`; `plots.py` only draws; `builder.py` wires them together. To add a report type, subclass `CalibrationReport`, override the `extra_plots` and `extra_summary` hooks, and select it in `make_report`.
- **Regression checks.** Before and after any refactor, run a short calibration (`max_runs = 5`) on the test project with `early_stop = false` and compare `model_iterations.csv`. Differences in the fourth significant figure are expected only when unit constants change.
- **Deprecated.** `raster_processing.py` is superseded by `shape_export.py`. `FlowFileParser.update_unsteady_flow` and `PlanFileParser.update_simulation_date` are marked deprecated in their docstrings. The old notebook reports (`HECRAS_Calibration_Report.ipynb`, `HECRAS_Indirect_Report.ipynb`) were replaced by the `reporting` package.
- **Known loose ends.** `generate_ratingcurve` and `sim_event` assume the first observation point is the gauge cell. Batch mode is implemented for `cal_observed` only, and has no report. `HydraulicModel` is an empty base class.
