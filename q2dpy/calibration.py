"""Model calibration: observation loading, objective function, and optimizer drivers."""
import random
import time
from functools import partial

import numpy as np
import pandas as pd
import sambo
import scipy.optimize
from collections import deque

import config
from csv_log import append_row, next_iteration
from model import HecRas
from objectivefun import obj_func


# --------------------------------------------------------------- validations
def check_model_names(hecmodel):
    """Stops early if a Manning's n region named in the config is not in the land-cover file."""
    wanted = set()
    if any([config.cal_observed, config.cal_indirect]):
        wanted |= set(config.Man_n_params)
    if config.gen_ratecurv is True and config.adjust_n_rating:
        wanted |= set(config.n_regions)
    if not wanted:
        return
    man_tab = hecmodel.get_Mannings_calibration_regions(config.lchdf_filename)
    present = set(hecmodel.binary_to_string([row[0] for row in man_tab]))
    missing = sorted(wanted - present)
    if missing:
        raise SystemExit(f"Config errors:\n  - Region(s) not found in the land-cover HDF: {missing}. "
                         f"Available: {sorted(present)}")


# --------------------------------------------------------------- observations
def required_obs_columns():
    """Columns the observation csv must contain for the current run mode.

    Calibration needs the measured elevation and the mesh cell of each point;
    batch mode also needs the discharge of each row. Other modes (rating curve,
    sim event) only need the cell index.
    """
    if any([config.cal_observed, config.cal_indirect, config.cal_EG_slope]):
        if config.batch_process is True:
            return ['Cell_Index', 'Elev_m', 'Q(cfs)']
        return ['ID', 'Cell_Index', 'Channel_Distance', 'Elev_m']
    return ['Cell_Index']


def load_obs_df():
    """Reads the observation csv (config.wse_filename) and checks that the columns
    needed for the current run mode are present. Returns the DataFrame."""
    obs_df = pd.read_csv(config.wse_filename)
    missing = [col for col in required_obs_columns() if col not in obs_df.columns]
    if missing:
        raise ValueError(f"{config.wse_filename} is missing required column(s): {missing}")
    return obs_df


# ------------------------------------------------------------------- simplex
def create_i0_simplex(i0_guess, seed=None):
    """Creates the initial Nelder-Mead simplex from (low, high) guesses per parameter.

    Row 0 is all lower bounds, the last row is all upper bounds, and the rows in
    between are random draws inside each range (n parameters give n+1 vertices).
    """
    rng = random.Random(seed)
    rows = [[lo for lo, hi in i0_guess]]
    for _ in range(len(i0_guess) - 1):
        rows.append([round(rng.uniform(lo, hi), 3) for lo, hi in i0_guess])
    rows.append([hi for lo, hi in i0_guess])
    return np.array(rows)


# ------------------------------------------------- objective function pieces
def apply_friction_slopes(hecmodel, input_vals):
    """Applies us/ds friction slopes taken from the front of input_vals to the
    model's flow file. Returns the remaining (non-slope) values."""
    params = config.FS_params
    us = ds = None
    n = 0
    if 'us_fs' in params:
        us = input_vals[n]
        n += 1
    if 'ds_fs' in params:
        ds = input_vals[n]
        n += 1
    if us is not None or ds is not None:
        hecmodel.change_friction_slopes(us_norm=us, ds_norm=ds)
    return input_vals[n:]


def apply_trial_parameters(hecmodel, input_vals):
    """Writes one set of trial parameters from the optimizer into the model files.

    Order of values in input_vals: friction slopes (if cal_EG_slope), then
    Manning's n per region, then discharge (cal_indirect only).
    Returns the dictionary of new Manning's n values, or None if none were set.
    """
    # Manning's n calibration parameters, binary encoded for the landcover hdf
    man_n_params_bn = hecmodel.string_to_binary(config.Man_n_params)

    # friction slopes come first in input_vals; this consumes them
    if config.cal_EG_slope is True:
        input_vals = apply_friction_slopes(hecmodel, input_vals)

    new_n = None
    if config.cal_observed is True:
        # remaining values are Manning's n
        new_n = hecmodel.assign_param_vals(input_vals, man_n_params_bn)
        hecmodel.change_Base_Mannings(config.ghdf_filename, config.lchdf_filename, new_n)

    elif config.cal_indirect is True:
        # remaining values are Manning's n, with discharge last
        new_n = hecmodel.assign_param_vals(input_vals[:-1], man_n_params_bn)
        hecmodel.change_Base_Mannings(config.ghdf_filename, config.lchdf_filename, new_n)
        hecmodel.change_unsteady_flow(input_vals[-1])

    elif config.cal_EG_slope is not True:
        print("Give me some Direction Here")

    return new_n


def run_and_read_wse(hecmodel):
    """Runs the HEC-RAS plan and returns the water surface elevation of every
    mesh cell at the last simulation time step."""
    hecmodel.run_model()
    time.sleep(4)   # needed: the plan hdf isn't ready right after run_model returns

    phdf = hecmodel.load_current_plan_results(config.phdf_filename)
    # wse from last time step of simulation
    return phdf[-1]


def collect_param_row(hecmodel, new_n):
    """Reads the Manning's n value of each calibration region back from the
    landcover file and returns them as {region name: value} for the log.

    Includes a 'Structures' entry when config.structures is on.
    """
    man_tab = hecmodel.get_Mannings_calibration_regions(config.lchdf_filename)
    param_names = hecmodel.binary_to_string([i[0] for i in man_tab])
    param_vals = np.array([n[1] for n in man_tab])

    if config.structures is True:
        if new_n is None:
            raise ValueError("config.structures needs a Manning's n calibration mode "
                             "(cal_observed or cal_indirect)")
        param_names.append('Structures')
        if config.independent_structures is True:
            param_vals = np.append(param_vals, new_n[b'Structures'])
        else:
            param_vals = np.append(param_vals, new_n[b'Channel'])

    return dict(zip(param_names, param_vals.tolist()))


def score_model(ras_wse, obs_df, batch_row=None):
    """Compares modeled and observed water surface elevations.

    In batch mode, scores the single observation in batch_row; otherwise scores
    every point in obs_df. The modeled values are written into
    batch_row['Modeled_WSE'] or obs_df['Modeled_WSE'].
    Returns (objective function value, modeled WSE at the observation point(s)).
    """
    if batch_row is not None:
        ras_wse_pnts = ras_wse[batch_row['Cell_Index'].astype(int).tolist()]
        batch_row['Modeled_WSE'] = ras_wse_pnts
        rmse = obj_func(batch_row['Modeled_WSE'], batch_row['Elev_m'])
    else:
        # water surface elevation at reference points for this model run
        ras_wse_pnts = ras_wse[obs_df['Cell_Index'].astype(int).tolist()]
        obs_df['Modeled_WSE'] = ras_wse_pnts
        rmse = obj_func(obs_df['Modeled_WSE'], obs_df['Elev_m'])
    return rmse, ras_wse_pnts


def log_iteration(hecmodel, params_row, q_val, rmse, iteration, batch_row=None, obj_std=None):
    """Appends this model run to the iterations csv (parameters, discharge, objective value,
    and the std of the last two simplexes' worth of objective values).

    Batch runs also record the observed discharge, observed elevation and modeled
    elevation; normal runs record the friction slopes when they are being calibrated.
    """
    q_col = '{0}'.format(config.Q_params[0])

    row_out = dict(params_row)
    row_out[q_col] = q_val
    if batch_row is None and config.cal_EG_slope is True:
        slopes = hecmodel.read_friction_slopes()
        row_out['us_fs'] = slopes[0]
        row_out['ds_fs'] = slopes[-1]
    row_out['iteration'] = iteration
    row_out['Obj_Func_Value'] = rmse
    row_out['Obj_Std'] = obj_std
    if batch_row is not None:
        row_out['Q(cfs)'] = batch_row['Q(cfs)']
        row_out['Elev_m'] = batch_row['Elev_m']
        row_out['Modeled_WSE'] = batch_row['Modeled_WSE']
        row_out['Batch_Row'] = batch_row.name
    append_row(config.iterations_filename, row_out)


def log_wse_profile(obs_df, ras_wse_pnts, iteration):
    """Adds the modeled WSE profile of this iteration as a new column ('I<n>')
    of the WSE profile csv, creating the file from the observation points on the first run."""
    if config.wse_prof_filename.is_file():
        cell_df = pd.read_csv(config.wse_prof_filename)
    else:
        cell_df = obs_df[['ID', 'Cell_Index', 'Channel_Distance', 'Elev_m']].copy()
    cell_df['I{0}'.format(iteration)] = ras_wse_pnts
    cell_df.to_csv(config.wse_prof_filename, index=False)


def calc_obj_function(input_vals, obs_df=None, batch_row=None, tracker=None, cache=None):
    """Objective function called by the optimizer.

    Applies the trial parameters, runs HEC-RAS, compares modeled and observed
    water surface elevations, logs the iteration (with the running std of the
    objective value), and returns the objective value (RMSE or MAE) to minimize.

    If cache (a dict) is given, a parameter set that was already run during this
    optimization returns its stored objective value without running HEC-RAS again.
    Repeats are not logged and do not enter the convergence window.
    """
    # round inputs to 10^-6
    input_vals = [round(x, 6) for x in input_vals]

    key = tuple(input_vals)
    if cache is not None and key in cache:
        if batch_row is not None or config.verbose is True:
            print(f"Repeat of an earlier trial {key}; using stored RMSE: {cache[key]}")
            print("")
        return cache[key]

    hecmodel = HecRas.from_config()
    new_n = apply_trial_parameters(hecmodel, input_vals)
    ras_wse = run_and_read_wse(hecmodel)

    params_row = collect_param_row(hecmodel, new_n)
    q_val = hecmodel.get_inflow()[-1, 1]            # upstream boundary condition inflow
    iteration = next_iteration(config.iterations_filename)

    rmse, ras_wse_pnts = score_model(ras_wse, obs_df, batch_row)
    if batch_row is not None or config.verbose is True:
        print(f"RMSE: {rmse}")
        print("")

    if cache is not None:
        cache[key] = rmse

    obj_std = tracker.add(rmse) if tracker is not None else None

    log_iteration(hecmodel, params_row, q_val, rmse, iteration, batch_row, obj_std)
    if batch_row is None:
        log_wse_profile(obs_df, ras_wse_pnts, iteration)

    return rmse


# ------------------------------------------------------------------ optimizer
def optimize_model(initial_simplex=None, obs_df=None, batch_row=None):
    """Builds the starting parameter vector from the config, then runs the chosen
    optimizer (Nelder-Mead or SCE-UA) on calc_obj_function. Stops early when the
    objective values flatten out, if config.early_stop is on."""

    if config.cal_observed is True:
        if config.cal_EG_slope is True:
            initial_values = list(config.friction_slope)
        elif config.independent_structures is True:
            initial_values = list(config.Man_n_vals)
            initial_values.append(config.Man_n_vals[0])
        else:
            initial_values = list(config.Man_n_vals)
    elif config.cal_indirect is True:
        initial_values = []
        if config.cal_EG_slope is True:
            initial_values = list(config.friction_slope)
        initial_values.extend(config.Man_n_vals)
        if config.independent_structures is True:
            initial_values.append(config.Man_n_vals[0])
        initial_values.append(config.Q_params_vals[0])
    elif config.cal_EG_slope is True:
        initial_values = list(config.friction_slope)
    else:
        print('No defined computational method')
        return

    # tracks the spread of the last two simplexes' worth of objective values;
    # always records it, only stops the run when early_stop is on
    early_stop = getattr(config, 'early_stop', False) is True
    simplex_size = len(initial_values) + 1
    tracker = ConvergenceTracker(2 * simplex_size,
                                 tol=config.early_stop_tol if early_stop else None)
    callback = tracker.callback if early_stop else None

    # one cache per optimization, so every batch row starts empty
    objective = partial(calc_obj_function, obs_df=obs_df, batch_row=batch_row,
                        tracker=tracker, cache={})

    x0 = np.array(initial_values)
    bounds = config.bounds
    print(f"Initial Values: {initial_values}")
    print(f"Bounds: {bounds}")

    if config.algorythm.lower() == 'nelder-mead':
        options = {'xatol': 1e-4, 'maxiter': config.max_runs, 'disp': True}
        if initial_simplex is not None:
            options['initial_simplex'] = initial_simplex
        result = scipy.optimize.minimize(objective, x0, method='Nelder-Mead',
                                         bounds=bounds, options=options, callback=callback)
        print(f"Nelder-Mead result: {result}")

    elif config.algorythm.lower() == 'sce-ua':
        kw = dict(method='sceua', bounds=bounds, tol=1e-4, max_iter=config.max_runs,
                  disp=True, kwargs={'n_complexes': 3, 'complex_size': 2}, callback=callback)
        if initial_simplex is not None:
            kw['initial_simplex'] = initial_simplex
        result = sambo.minimize(objective, initial_values, **kw)
        print(f"SCE-UA result: {result}")

    else:
        print("Invalid Optimization Algorithm")


class ConvergenceTracker:
    """Tracks the spread of the most recent objective values to detect a plateau.

    Keeps the last n_values objective values (use two simplexes' worth:
    2 * (number of parameters + 1)). std is the standard deviation of that window,
    or None until the window is full. If tol is given, the run counts as converged
    once std < tol.
    """

    def __init__(self, n_values, tol=None):
        self.recent = deque(maxlen=n_values)
        self.tol = tol
        self.std = None

    def add(self, value):
        """Records one objective value; returns the std of the current window (or None)."""
        self.recent.append(value)
        if len(self.recent) == self.recent.maxlen:
            self.std = float(np.std(self.recent))
        return self.std

    @property
    def converged(self):
        return self.tol is not None and self.std is not None and self.std < self.tol

    def callback(self, intermediate_result):
        """Optimizer callback: ends the run (cleanly, keeping the best result) once converged."""
        if self.converged:
            print(f"Converged: std of the last {len(self.recent)} objective values is "
                  f"{self.std:.2e} (< {self.tol}). Stopping.")
            raise StopIteration