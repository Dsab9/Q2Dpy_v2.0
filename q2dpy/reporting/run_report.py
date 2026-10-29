"""Build a calibration report for a finished run without rerunning the model."""
from reporting import make_report

# ============================== EDIT THESE ====================================
OUTPUT_DIR = r"C:\Users\CND367\Documents\Python_Scripts\Q2Dpy\test_data\Output\test_sub"
TOL_M = 0.03          # e.g. 0.03 to override [report] report_tol_m for this report only
# ==============================================================================

if __name__ == "__main__":
    make_report(OUTPUT_DIR, tol_m=TOL_M).run()