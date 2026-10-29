"""Launches Q2Dpy and runs the workflow selected in the site config."""

import os

import config
from calibration import create_i0_simplex, load_obs_df, optimize_model, check_model_names
from csv_log import append_last_row
from grid import get_cell_index
from model import HecRas
from rating_curve import generate_ratingcurve, sim_event
from reporting import make_report
from units import cfs_to_cms


def main():
    config.validate()
    config.start_run()                      # creates Input/<run> and Output/<run>
    if config.find_cell_index is True:
        get_cell_index(config.grid_filename, config.wse_filename)
    config.snapshot_inputs()                # after the cell-index step, so the copied CSV is the one used

    # Load measured WSE data (checks the columns this run mode needs)
    obs_df = load_obs_df()

    # one model handle for all setup steps (it only stores file paths)
    hecmodel = HecRas.from_config()
    check_model_names(hecmodel)

    if config.set_datetime is True:
        hecmodel.update_datetime()

    if config.set_friction_slope is True:
        hecmodel.change_friction_slopes(us_norm=config.friction_slope[0],
                                        ds_norm=config.friction_slope[-1])

    if config.cal_observed is True:
        hecmodel.change_unsteady_flow(config.Q_params_vals)

    # set working directory to this run's output folder
    os.chdir(config.output_directory)

    # run optimization
    if any([config.cal_indirect, config.cal_observed, config.cal_EG_slope]):
        i0_simp = None
        if config.create_i0_simplex is True:
            i0_simp = create_i0_simplex(config.i0_guess)
            print(f"initial simplex: {i0_simp}")

        if config.batch_process is not True:
            optimize_model(i0_simp, obs_df)
        else:
            for index, row in obs_df.iterrows():
                hecmodel.change_unsteady_flow([round(cfs_to_cms(row['Q(cfs)']), 3)])
                optimize_model(i0_simp, obs_df, batch_row=row)
                append_last_row(config.iterations_filename, config.batch_filename)

    # option to generate hydrograph, currently only works by itself.
    if config.gen_ratecurv is True:
        if config.use_Q_list is False:
            generate_ratingcurve(obs_df, config.min_q, config.max_q, config.q_divisions)
        else:
            generate_ratingcurve(obs_df)
    elif config.sim_event is True:
        sim_event(config.max_q, obs_df)

    # create calibration report
    if any([config.cal_indirect, config.cal_observed]):
        try:
            report_dir = make_report(config.output_directory).run()
            print(f"Report is in {report_dir}")
        except Exception as exc:
            print(f"Report failed ({exc!r}). Results are saved; rerun it with: "
                  f"python -m reporting {config.output_directory}")

    print(f"Done. Outputs are in {config.output_directory}")



if __name__ == "__main__":
    main()
