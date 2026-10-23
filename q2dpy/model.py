import os
import time

import h5py
import numpy as np
import shapely
import win32com.client

import config
from rasfileparser import FlowFileParser, PlanFileParser


class HydraulicModel:
    """Don't remember what my plans for this were, but it's not hurting anything..."""
    def __init__(self):
        pass


class HecRas(HydraulicModel):
    """Class that makes changes to RAS parameter files"""

    def __init__(self, project_file, geom_hdf, plan_hdf, flowfile, planfile, landcover_hdf):
        super().__init__()
        self.project_path = project_file
        self.geom_hdf = geom_hdf
        self.plan_hdf = plan_hdf
        self.flowfile = flowfile
        self.planfile = planfile
        self.landcover_hdf = landcover_hdf

    @classmethod
    def from_config(cls):
        """HecRas handle built from the current config."""
        return cls(config.prj_filename, config.ghdf_filename, config.phdf_filename,
                   config.flow_filename, config.plan_filename, config.lchdf_filename)

    def change_unsteady_flow(self, q_val):
        """updates discharge to upstream boundary condition"""
        u0file = FlowFileParser(self.flowfile)
        # p0file = PlanFileParser(self.planfile)
        u0file.format_hydrograph_input(q_val)
        # p0file.update_simulation_date(time_series)

    def change_friction_slopes(self, us_norm=None, ds_norm=None):
        """updates energy gradient at upstream and/or downstream boundary condition"""
        u0file = FlowFileParser(self.flowfile)
        if us_norm is not None:
            u0file.update_us_EGslope(us_norm)
        if ds_norm is not None:
            u0file.update_ds_EGslope(ds_norm)

    def read_friction_slopes(self):
        """checks energy gradient at upstream and downstream boundary condition"""
        u0file = FlowFileParser(self.flowfile)
        us_slope = u0file.read_us_EGslope()
        ds_slope = u0file.read_ds_EGslope()
        slope_list = [us_slope, ds_slope]
        return slope_list

    def update_datetime(self):
        """sets date and time in RAS plan file"""
        planfile = PlanFileParser(self.planfile)
        planfile.update_datetime()

    def get_inflow(self):
        """gets current discharge at upstream boundary condition"""
        with h5py.File(self.plan_hdf, 'r') as phf:
            sg_flw_tab = phf[f'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
                             f'Boundary Conditions/{config.us_bc}']
            sg_flw_arr = np.array(sg_flw_tab)

        return sg_flw_arr

    def run_model(self):
        """ Runs the saved Hec-Ras project file and closes upon completion"""
        hec = win32com.client.Dispatch(f"RAS{config.hec_version}.HECRASController")
        hec.QuitRas()
        hec.ShowRas()  # show HEC-RAS window
        # full filename of the RAS project
        RASProject = os.path.join(os.getcwd(), self.project_path)
        hec.Project_Open(RASProject)
        # to be populated: number and list of messages, blocking mode
        NMsg, TabMsg, block = None, None, True
        # computations of the current plan
        hec.Compute_CurrentPlan(NMsg, TabMsg, block)
        time.sleep(4)
        hec.QuitRas()  # close HEC-RAS
        del hec  # delete HEC-RAS controller


    def get_GIS(self):
        """Exports sdf file with cross-section data for use with HEC-GeoRAS """
        # Not Utilized
        hec = win32com.client.Dispatch(f"RAS{config.hec_version}.HECRASController")
        hec.QuitRas()
        hec.ShowRas()  # show HEC-RAS window
        # full filename of the RAS project
        RASProject = os.path.join(os.getcwd(), self.project_path)
        hec.Project_Open(RASProject)
        hec.ExportGIS()
        hec.QuitRas()  # close HEC-RAS
        del hec  # delete HEC-RAS controller

    def get_2D_refinement_region(self, geometry_hdf):
        """gets shapefile of all refinement regions on geometry file"""
        with h5py.File(geometry_hdf, 'r') as ghf:
            Ref_Reg_Pnts = ghf["Geometry/2D Flow Area Refinement Regions/Polygon Points"]
            Ref_Reg_array = np.array(Ref_Reg_Pnts)
            geom = shapely.geometry.Polygon(Ref_Reg_array)
        return geom

    def load_current_plan_results(self, currentPlanFile):
        """Load the current plan results and returns array of final wse in each cell"""

        # check whether the hdf file exists
        if not os.path.isfile(currentPlanFile):
            raise Exception(
                "The result HDF file for current plan does not exist."
                " Make sure to run HEC-RAS before calling this function.")
        else:
            with h5py.File(currentPlanFile, 'r') as rslt:
                WSE = np.array(rslt[f"Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/"
                                    f"2D Flow Areas/{config.perimeter}/Water Surface"])

        return WSE

    def extract_WSE_timeseries(self, grid_cells, currentPlanFile):
        """not sure what this des or why it's here"""
        wat_el = self.load_current_plan_results(currentPlanFile)
        ref_pnts = wat_el[grid_cells, :]
        return ref_pnts

    def get_Mannings_calibration_regions(self, landcover_hdf):
        """gets lancover regions from file, returns them as an array"""
        with h5py.File(landcover_hdf, 'r') as lchf:
            Man_tab = lchf["Variables"][:]
            Nw_arr = np.array(Man_tab)
        return Nw_arr

    def change_Base_Mannings(self, geometry_hdf, landcover_hdf, new_param_dict):
        """Changes Manning's n values for calibration regions in Landcover File"""
        Man_n = self.get_Mannings_calibration_regions(landcover_hdf)
        updt_man = Man_n.copy()
        new_params = new_param_dict

        new_n_vals = []
        for i in updt_man:
            if i[0] in new_params.keys():
                nval = np.float32(new_params[i[0]])
                n = i
                n[1] = nval
            else:
                n = i
            new_n_vals.append(n)
        new_n_vals = np.array(new_n_vals)

        just_nval = np.array([n[1] for n in new_n_vals])

        if config.verbose is True:
            # print(f"existing n values: {updt_man}")
            # print(f"new n values: {new_n_vals}")
            print(f"updated n values: {new_params}")

        with h5py.File(config.lchdf_filename, 'r+') as lchf:
            Man_tab = lchf["Variables"]
            Man_tab["ManningsN"] = just_nval
            lchf.close()

        with h5py.File(landcover_hdf, 'r') as lchdf:
            Man_check = lchdf["Variables"][:]
            Man_check = np.array(Man_check)
            lchf.close()
        if not np.array_equal(Man_check, new_n_vals):
            raise ValueError('LandCover.hdf save was unsuccessful/corrupted')

        # this changes the structure n val to that of the channel
        land_class_list = []
        for i in new_n_vals:
            land_class_list.append(i[0])
        if config.structures is True:
            if b'Structures' in new_params and config.independent_structures is True:
                br_n_val = new_params[b'Structures']

            else:
                br_n_val = new_params[b'Channel']

            with h5py.File(geometry_hdf, 'r+') as rslt:
                structure_n = rslt["Geometry/Structures/Mannings Data"]
                structure_array = np.array(structure_n)
                structure_array[:, 1] = br_n_val
                structure_n[...] = structure_array

            with open(config.geom_filename, 'r', encoding='utf-8') as geom_file:
                lines = geom_file.readlines()

            str_val = str(br_n_val).split('.')[1]
            new_line = f'       0   .{str_val}\n'
            n_line_list = []
            for num, line in enumerate(lines, 0):
                if 'Conn BR: BR Mann=' in line or 'Conn BR: XS Mann=' in line:
                    n_num = int(num + 1)
                    n_line_list.append(n_num)
            for i in n_line_list:
                lines[i] = new_line

            with open(config.geom_filename, 'w', encoding='utf-8') as geom_file:
                geom_file.writelines(lines)

            # print(f"bridge channel n val set to: {structure_array[0]}")

    def assign_param_vals(self, n, params_list):
        """Gets new manning's n values formatted to be passed into Landcover file"""
        if len(n) != len(params_list):
            if config.independent_structures is True:
                params_list.append(b'Structures')
                new_param_vals = dict(zip(params_list, n))
            elif len(n) == 1:
                nvals = np.full(len(params_list), n).tolist()
                new_param_vals = dict(zip(params_list, nvals))
                print(
                    "Only 1 new parameter value given with >1 parameters to change:\n "
                    "Assigning one value to all parameters")
            else:
                print(f"params_list: {params_list}; n: {n}")
                raise ValueError(
                    "Number of new values is >1 but < number of parameters to change. No parameter values assigned.")
        else:
            new_param_vals = dict(zip(params_list, n))
        return new_param_vals

    def string_to_binary(self, string):
        """returns list of strings formatted in binary, what did you think it did?"""
        # input string or list of strings
        if type(string) is list:
            binary_lst = []
            for i in string:
                bn = bytes(i, 'utf-8')
                binary_lst.append(bn)
        else:
            binary_lst = bytes(string, 'utf-8')
        return binary_lst

    def binary_to_string(self, binry):
        """returns list of ascii strings from a binary formatted strig"""
        # input encoded object or list of encoded binary objects
        if type(binry) is list:
            st_lst = []
            for i in binry:
                st = i.decode()
                st_lst.append(st)
        else:
            st_lst = binry.decode()
        return st_lst
