"""Module that returns n value given trend type and parameters"""

import numpy as np


def linear(x, a, b):
    return a * x + b


def log(x, a, b):
    return a * np.log(x) + b


def exp(x, a, b):
    return a * np.exp(x) + b


def power(x, a, b):
    return a * x ** b


def hyper(x, a, b):
    return a / x + b


def adjust_n(func, x, a, b):
    if func == 'linear':
        return linear(x, a, b)
    if func == 'log':
        return log(x, a, b)
    if func == 'exp':
        return exp(x, a, b)
    if func == 'power':
        return power(x, a, b)
    if func == 'hyper':
        return hyper(x, a, b)
