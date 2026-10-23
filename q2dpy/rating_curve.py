"""Rating curve generation and single-event simulation."""
import pandas as pd

import aquarius
import config
import n_adjuster
import shape_export
from csv_log import append_row
from model import HecRas
from units import cfs_to_cms, cms_to_cfs, m_to_ft


def adjusted_n_values(q_cms):
    """Manning's n per region for a given discharge, clamped to [min_n, max_n]."""
    new_man = []
    for i in range(len(config.a)):
        n = n_adjuster.adjust_n(config.function_type[i], q_cms, config.a[i], config.b[i])
        if config.max_n[i] < config.min_n[i]:
            raise Exception("Minimum n-value is larger than Maximum n-Value")
        if n > config.max_n[i]:
            n = config.max_n[i]
        if n < config.min_n[i]:
            n = config.min_n[i]
        new_man.append(round(n, 6))
    return new_man


def build_rating_row(wse_m, q_cms, n_values=None):
    """One row of the rating curve csv."""
    stage_m = wse_m - config.gauge_el_NAVD88m
    row = {'Elev_orif': config.gauge_el_NAVD88m,
           'WSE(m)': round(wse_m, 3),
           'stage(m)': round(stage_m, 3),
           'Q(m^3/s)': round(q_cms, 3),
           'stage(ft)': round(m_to_ft(stage_m), 3),
           'Q(cfs)': round(cms_to_cfs(q_cms), 1)}
    if n_values is not None:
        row.update(zip(config.n_regions, n_values))
    return row


def export_inundation(wse_m):
    """Saves the inundation shapefile / GeoJSON for the modeled water surface."""
    if config.export_shapefile is True:
        shape_export.export_shapefile()
        if config.export_geojsons is True:
            stage_ft = m_to_ft(wse_m - config.gauge_el_NAVD88m)
            shape_export.saveas_geojson(stage_ft)


def run_one_discharge(q_cms, obs_df):
    """Runs the model at one discharge (m^3/s) and logs a rating-curve row."""
    hecmodel = HecRas.from_config()
    hecmodel.change_unsteady_flow(q_cms)

    new_man = None
    if config.adjust_n_rating is True:
        new_man = adjusted_n_values(q_cms)
        man_n_params_bn = hecmodel.string_to_binary(config.n_regions)
        new_n = hecmodel.assign_param_vals(new_man, man_n_params_bn)
        hecmodel.change_Base_Mannings(config.ghdf_filename, config.lchdf_filename, new_n)

    # Run RAS
    hecmodel.run_model()

    phdf = hecmodel.load_current_plan_results(config.phdf_filename)
    # last time step of simulation
    ras_wse = phdf[-1]
    # water surface elevation at the reference point for this run
    wse_m = ras_wse[obs_df['Cell_Index'].astype(int).tolist()][0]
    print(f"WSE: {wse_m}m")

    export_inundation(wse_m)
    append_row(config.rating_curve_filename, build_rating_row(wse_m, q_cms, new_man))


def generate_ratingcurve(obs_df, min_q=None, max_q=None, max_runs=None):
    """Runs the model over a range of discharges (min_q..max_q in max_runs steps)
    or over the Q_list csv when min_q is None. Outputs the rating curve csv."""
    if min_q is not None:
        q_increment = (max_q - min_q) / max_runs
        q_values = [(run * q_increment) + min_q for run in range(1, max_runs + 1)]
    else:
        q_list_cfs = pd.read_csv(config.q_list)['Q(cfs)'].to_list()
        q_values = [round(cfs_to_cms(q), 3) for q in q_list_cfs]

    for q in q_values:
        run_one_discharge(q, obs_df)


def sim_event(inst_q, obs_df):
    """Runs the model for one discharge (m^3/s), optionally the current site discharge."""
    if config.get_inst_q is True:
        q_val = aquarius.get_site_Q()
        if q_val == 0:
            raise ValueError("No site discharge data found")
    else:
        q_val = inst_q

    hecmodel = HecRas.from_config()
    hecmodel.change_unsteady_flow(q_val)

    # Run RAS
    hecmodel.run_model()

    phdf = hecmodel.load_current_plan_results(config.phdf_filename)
    ras_wse = phdf[-1]
    wse_m = float(ras_wse[obs_df['Cell_Index'].astype(int).tolist()][0])
    export_inundation(wse_m)