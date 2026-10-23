"""Small helpers for the csv logs Q2Dpy writes (iterations, rating curve, batch)."""
from pathlib import Path

import pandas as pd


def next_iteration(path):
    """Iteration number for the next row of a log csv (1 if the file doesn't exist yet)."""
    path = Path(path)
    if not path.is_file():
        return 1
    return int(pd.read_csv(path)['iteration'].iloc[-1]) + 1


def append_row(path, row):
    """Appends one row (dict) to a csv, creating the file if needed."""
    path = Path(path)
    new_df = pd.DataFrame([row])
    if path.is_file():
        new_df = pd.concat([pd.read_csv(path), new_df], ignore_index=True)
    new_df.to_csv(path, index=False)


def append_last_row(src_path, dst_path):
    """Copies the last row of one csv onto the end of another (used for batch results)."""
    src_path, dst_path = Path(src_path), Path(dst_path)
    last_row = pd.read_csv(src_path).iloc[-1:]
    if dst_path.is_file():
        last_row = pd.concat([pd.read_csv(dst_path), last_row], ignore_index=True)
    last_row.to_csv(dst_path, index=False)