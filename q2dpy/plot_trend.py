"""Module that produces trendlines for relationship between modeled Q & channel n values"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

import config


class TrendLine:
    def __init__(self):
        self.data = pd.read_csv(config.trendline)
        self.x = self.data['X'].iloc[1:].astype(float)
        self.y = self.data['Y'].iloc[1:].astype(float)
        self.x_title = self.data['X'].iloc[0]
        self.y_title = self.data['Y'].iloc[0]

    def linear(self):
        x = self.x
        y = self.y

        def func(x, a, b):
            return a * x + b

        popt, pcov = curve_fit(func, x, y)
        a, b = popt
        x_fitted = np.linspace(np.min(x), np.max(x), 100)
        y_fitted = func(x_fitted, a, b)

        plt.scatter(x, y)
        plt.plot(x_fitted, y_fitted, 'r', label='Fitted curve')
        plt.title(f"y = {a.round(6)}x + {b.round(6)}")
        print(f"{a.round(6)}x + {b.round(6)}")
        plt.xlabel(self.x_title)
        plt.ylabel(self.y_title)
        plt.show()

    def log(self):
        x = self.x
        y = self.y

        def func(x, a, b):
            return a * np.log(x) + b

        popt, pcov = curve_fit(func, x, y)
        a, b = popt
        x_fitted = np.linspace(np.min(x), np.max(x), 100)
        y_fitted = func(x_fitted, a, b)

        plt.scatter(x, y)
        plt.plot(x_fitted, y_fitted, 'r', label='Fitted curve')
        plt.title(f"y = {a.round(6)}log(x) + {b.round(6)}")
        print(f"{a.round(10)}log(x) + {b.round(10)}")
        plt.xlabel(self.x_title)
        plt.ylabel(self.y_title)
        plt.show()

    def exp(self):
        x = self.x
        y = self.y

        def func(x, a, b):
            return a * np.exp(x) + b

        popt, pcov = curve_fit(func, x, y)
        a, b = popt
        x_fitted = np.linspace(np.min(x), np.max(x), 100)
        y_fitted = func(x_fitted, a, b)

        plt.scatter(x, y)
        plt.plot(x_fitted, y_fitted, 'r', label='Fitted curve')
        plt.title(f"y = {a.round(6)}e^x + {b.round(6)}")
        print(f"{a.round(6)}e^x + {b.round(6)}")
        plt.xlabel(self.x_title)
        plt.ylabel(self.y_title)
        plt.show()

    def power(self):
        x = self.x
        y = self.y

        def func(x, a, b):
            return a * x ** b

        popt, pcov = curve_fit(func, x, y)
        a, b = popt
        x_fitted = np.linspace(np.min(x), np.max(x), 100)
        y_fitted = func(x_fitted, a, b)

        plt.scatter(x, y)
        plt.plot(x_fitted, y_fitted, 'r', label='Fitted curve')
        plt.title(f"y = {a.round(6)}^x + {b.round(6)}")
        print(f"{a.round(6)}^x + {b.round(6)}")
        plt.xlabel(self.x_title)
        plt.ylabel(self.y_title)
        plt.show()

    def hyper(self):
        x = self.x
        y = self.y

        def func(x, a, b):
            return a / x + b

        popt, pcov = curve_fit(func, x, y)
        a, b = popt
        x_fitted = np.linspace(np.min(x), np.max(x), 100)
        y_fitted = func(x_fitted, a, b)

        plt.scatter(x, y)
        plt.plot(x_fitted, y_fitted, 'r', label='Fitted curve')
        plt.title(f"y = {a.round(10)}/x + {b.round(10)}")
        print(f"{a.round(6)}/x + {b.round(6)}")
        plt.xlabel(self.x_title)
        plt.ylabel(self.y_title)
        plt.show()


tl = TrendLine()
tl.log()
