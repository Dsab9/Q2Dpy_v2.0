"""Config file for Q2Dpy, choose wisely"""

from pathlib import Path


# calibration config file
hec_version = '66'

cal_observed = False
cal_indirect = False
cal_EG_slope = False
gen_ratecurv = True
sim_event = False

batch_process = False  # will calibrate list of given discharges
create_i0_simplex = True # only works with Nelder-Mead
algorythm = 'Nelder-Mead'  # 'Nelder-Mead' 'SCE-UA'
objective_function = 'RMSE'  # 'RMSE' 'MAE'

structures = False  # will assign channel n to structures in cal_observed
independent_structures = False  # calibrates all structures separately from channel  (structures must be true)
EPSG = 'EPSG:6514'  # EPSG:6514 (NAD83 2011m MT state plane), EPSG:5703 (NAVD88 height m) use geiod2018
find_cell_index = False  # will get cell index from WSP coordinates and update csv
get_inst_q = False  # will grab current reporting discharge for specified gauge
export_shapefile = False  # for gen_ratecurve & sim_event, will save last inundation shapefile to Directory
export_geojsons = False  # for gen_ratecurve & sim_event, will save all inundation GeoJSON's to Directory (export shape must be True)

# define directories
Directory = Path(r'S:\AQMetadata\Water_Management\Site Models\41Q 06000 Belt Creek nr Belt, MT\HECRAS')
ras_directory = Path(f'{Directory}/RAS_files')
gis_directory = Path(f'{Directory}/GIS')
geojson_directory = Path(f'{Directory}/GIS/GeoJSONs')
input_directory = Path(f'{Directory}/Input')
output_directory = Path(f'{Directory}/Output')

# define relevant file paths, calibration parameters, and define channel centerline
prj = 'BeltCreek'
prj_filename = ras_directory.joinpath(f'{prj}.prj')
ghdf_filename = ras_directory.joinpath(f'{prj}.g07.hdf')
phdf_filename = ras_directory.joinpath(f'{prj}.p03.hdf')
geom_filename = ras_directory.joinpath(f'{prj}.g07')
flow_filename = ras_directory.joinpath(f'{prj}.u03')
plan_filename = ras_directory.joinpath(f'{prj}.p03')
lchdf_filename = ras_directory.joinpath('Land Classification', 'LandCover.hdf')

grid_filename = Path(f'{gis_directory}/flow_area.shp')  # for finding cell only
terrain_raster = Path(f'{gis_directory}/Terrain (1).Clone.tif')  # just a template for exporting wse's
wse_filename = Path(f'{input_directory}/batch_channel_cal.csv')  # water surface elevations for model calibration
trendline = Path(f'{input_directory}/trendline.csv') # Q vs channel n values for trend plotting
q_list = input_directory.joinpath('Q_list.csv')  # List of discharges for batch process

# Output filepaths
simplex_filename = Path(f'{output_directory}/simplex_dataframe.csv')
iterations_filename = Path(f'{output_directory}/model_iterations.csv')
wse_prof_filename = Path(f'{output_directory}/wse_profiles_output.csv')
rating_curve_filename = Path(f'{output_directory}/rating_curve.csv')
batch_filename = Path(f'{output_directory}/batch_results.csv')

set_friction_slope = False  # overrides friction slopes prior to initial run
FS_params = ['us_fs', 'ds_fs']  # can use one or both for cal_EG_slope, us_fs must be first if both
friction_slope = [0.003, 0.0025]

# define mannings values per region
Man_n_params = ['Channel']  # eg. 'Grassland', 'Road', 'NoData', 'Channel', 'Riparian'
Man_n_vals = [0.03]

Q_params = ['UpstreamBC']  # discharge is last in bounds/ initial guess
Q_params_cfs = 955.9  # 769.7
Q_params_vals = [round(Q_params_cfs * 0.02832, 3)]

# Order of inputs (us_fs, ds_fs, Man_n_params, structures, discharge)
bounds = [(0.015, 0.15)]
i0_guess = [(0.03, 0.035)]
max_runs = 250

gauge_el_NAVD88m = 865.194  # site specific

# Use below settings for gen_ratecurv = True
use_Q_list = True  # this uses a csv list of discharges from inputs rather than generating its own
min_cfs = 0
min_q = round(min_cfs * 0.02832, 3)
max_cfs = 420  # also used for sim event
max_q = round(max_cfs * 0.02832, 3)
q_divisions = 60  # number of runs, set to 1 if you want to generate single event based on q
adjust_n_rating = False  # this adjusts the  n value dependent on the discharge, input a b and trend params (log recommended)
#a = [-0.0198579780]
#b = [0.1178243443]
n_regions = ['Channel']
function_type = ['log']  # linear, log, exp, power, hyper  (note: x is metric)
max_n = [0.14]
min_n = [0.03]

# General settings
hydrograph_ramp = False  # True will generate hydrograph with incrementally increasing q with the last hour held at max, false will keep q constant
change_sim_time = False  # Changes sim time based on 15min input increments
sim_time_hr = 3  # min 1 hr
set_datetime = False  # True will allow for manual selection of hydrograph input time and enable the following settings
start_date = '07JUN2023'
start_time = '00:00'
end_date = '07JUN2023'
end_time = '03:00'
computation_interval = '0.5SEC'

#  Labeling Bugfix
perimeter = 'Perimeter'
us_bc = 'UpstreamBC'
ds_bc = 'DownstreamBC'
verbose = True

# TODO:
# add datetime range start to config, or pull from hecras?
# option on grab hydrograph from file and will adjust time params autmatically
