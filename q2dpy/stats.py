"""Plot stats from indirect model calibration, what they mean is up to you"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats

import config

if config.cal_indirect is True:
    param_df = pd.read_csv(config.iterations_filename)
    Q_data = param_df[config.Q_params[0]]
    final_simp = Q_data.tail(len(config.i0_guess) + 1)
    simp_len = len(final_simp)
    final_Q = np.mean(final_simp)
    mean = np.mean(Q_data)
    print(f"Final Q: {round(final_Q, 2)}m^3/s, or {round(final_Q / 0.02832, 1)}cfs")

    stdev = stats.tstd(Q_data)
    stdev_percent = round((stdev / final_Q * 100), 1)
    SE = round(stats.sem(Q_data), 4)
    print(f"SE = {SE}%")
    print(f"Q Std Dev = {round(stdev, 2)} m^3/s, +- {stdev_percent}%")

    z = stats.norm.interval(alpha=0.9, loc=mean, scale=stdev)
    z_val = (z[-1] - z[0]) / 2
    z_percent = round((z_val / final_Q * 100), 1)
    print(f"90% Confidence interval: {z} m^3/s, +-{z_val} m^3/s, +- {z_percent}%")

    z = stats.norm.interval(alpha=0.95, loc=mean, scale=stdev)
    z_val = (z[-1] - z[0]) / 2
    z_percent = round((z_val / final_Q * 100), 1)
    print(f"95% Confidence interval: {z} m^3/s, +-{z_val} m^3/s, +- {z_percent}%")

    norms = stats.norm.fit(Q_data)
    x = np.linspace(min(Q_data), max(Q_data), 100)
    pdf = stats.norm.pdf(x, *norms)

    plt.plot(x, pdf, label='Fitted Normal Distribution')
    plt.hist(Q_data, bins=30, density=True, alpha=0.5)
    plt.xlabel('Value')
    plt.ylabel('Probability Density')
    plt.legend()
    plt.show()

# TODO:
#       Option to drop 1st two simplices
#       Option to cut of stats analysis at x iteration
#       Option to specify file to run stats on
