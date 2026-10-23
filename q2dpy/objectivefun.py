"""calculates objective function from modeled and measured wse's"""

import numpy as np

import config


def obj_func(modeled, observed):
    """
    Parameters
    ----------
    modeled : numpy 1d array of modeled WSE at reference points.
    observed : numpy 1d array of the observed WSE at reference points.

    Returns
    -------
    scalar RMSE value
    or
    scalar MAE value

    RMSE recommended (large errors more heavily weighted)
    """

    if config.objective_function == 'RMSE':

        err = modeled - observed
        err_sqr = err ** 2
        RMSE = np.sqrt(err_sqr.mean())
        return RMSE

    elif config.objective_function == 'MAE':
        abs_err = abs(modeled - observed)
        MAE = abs_err.mean()
        return MAE

    else:
        print("No objective Function Defined!")
