"""Module that opens ras project currently specified in config file"""

import os
import win32com.client
import config

def launch_ras():
    hec = win32com.client.Dispatch(f"RAS{config.hec_version}.HECRASController")
    hec.QuitRas()
    hec.ShowRas()  # show HEC-RAS window
    # full filename of the RAS project
    RASProject = os.path.join(os.getcwd(), config.prj_filename)
    hec.Project_Open(RASProject)


if __name__ == "__main__":
    launch_ras()
