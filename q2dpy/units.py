"""Unit conversions used across Q2Dpy."""

CFS_TO_CMS = 0.02832
FT_TO_M = 0.3048


def cfs_to_cms(q_cfs):
    return q_cfs * CFS_TO_CMS


def cms_to_cfs(q_cms):
    return q_cms / CFS_TO_CMS


def m_to_ft(length_m):
    return length_m / FT_TO_M


def ft_to_m(length_ft):
    return length_ft * FT_TO_M