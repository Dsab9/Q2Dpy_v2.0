from pathlib import Path


# calibration config file
hec_version = '66'

cal_observed = False
cal_indirect = False
cal_EG_slope = False
gen_ratecurv = True
sim_event = False

batch_process = False
create_i0_simplex = True #only works for Nelder-Mead
algorythm = 'Nelder-Mead'  # 'Nelder-Mead' 'SCE-UA'
objective_function = 'RMSE'  # 'RMSE' 'MAE

structures = True  # will assign channel n to structures in cal_observed (currently assigns channel n to structure)
independent_structures = True  # calibrates all structures seperatly from channel input to simplex same as Q  (structures must be true)
EPSG = 'EPSG:6514'  # EPSG:6514 (NAD83 2011m MT state plane), EPSG:5703 (NAVD88 height m) use geiod2018
find_cell_index = False  # will get cell index from WSP coordinates and update csv
get_inst_q = False  # will grab current reporting discharge for gauge, will grab MaxQ if False
export_shapefile = False  # for gen_ratecurve & sim_event, will save last inundation shapefile to Directory
export_geojsons = False  # for gen_ratecurve & sim_event, will save all inundation GeoJSON's to Directory (export shape must be True)

# define directories
Directory = Path(r'C:\Users\CND641\Documents\41H 08990 Bozeman Cr\HECRAS')
ras_directory = Directory.joinpath('RAS_files')
gis_directory = Directory.joinpath('GIS')
geojson_directory = Directory.joinpath('GIS', 'GeoJSONs')
input_directory = Directory.joinpath('Input')
output_directory = Directory.joinpath('Output')

# define relevant file paths, calibration parameters, and define channel centerline
prj = 'bozo_cr'
prj_filename = ras_directory.joinpath(f'{prj}.prj')
ghdf_filename = ras_directory.joinpath(f'{prj}.g01.hdf')
phdf_filename = ras_directory.joinpath(f'{prj}.p06.hdf')
geom_filename = ras_directory.joinpath(f'{prj}.g01')
flow_filename = ras_directory.joinpath(f'{prj}.u05')
plan_filename = ras_directory.joinpath(f'{prj}.p06')
lchdf_filename = ras_directory.joinpath('Land Classification', 'LandCover.hdf')

grid_filename = Path(f'{gis_directory}/flow_area.shp')  # for finding cell only
# Cntrln_filename = Path(f'{gis_directory}/centerline.shp')  # depriciated
terrain_raster = Path(f'{gis_directory}/Terrain.tif')  # just a template for expoerting wse's
wse_filename = Path(f'{input_directory}/batch_channel_cal.csv')
trendline = Path(f'{input_directory}/trendline.csv')
q_list = input_directory.joinpath('Q_list.csv')

# Output filepaths
simplex_filename = output_directory.joinpath('simplex_dataframe.csv')
iterations_filename = output_directory.joinpath('model_iterations.csv')
wse_prof_filename = output_directory.joinpath('wse_profiles_output.csv')
rating_curve_filename = output_directory.joinpath('rating_curve.csv')
batch_filename = output_directory.joinpath('batch_results.csv')

set_friction_slope = False  # overrides friction slopes prior to initial run
FS_params = ['us_fs', 'ds_fs']  # can use one or both for cal_EG_slope, us_fs must be first if both
friction_slope = [0.003, 0.0025]

# define mannings values per region
Man_n_params = ['Channel']  # eg. 'Grassland', 'Road', 'NoData', 'Channel', 'Riparian'
Man_n_vals = [0.03]

Q_params = ['Upstream BC']  # discharge is last in bounds/ initial guess
Q_params_cfs = 2700.0
Q_params_vals = [round(Q_params_cfs * 0.02832, 3)]

# (us_fs, ds_fs, landcover_regions, structures, discharge)
bounds = [(0.01, 0.08), (0.01, 0.08)]
i0_guess = [(0.03, 0.035), (0.04, 0.045)]
max_runs = 250

gauge_el_NAVD88m = 1440.271  # site specific

# Settings for rating curve gen
use_Q_list = True  # this uses a csv list of discharges from inputs rather than generating its own
min_cfs = 0
min_q = round(min_cfs / 35.3147248276, 3)
max_cfs = 420  # also used for sim event
max_q = round(max_cfs / 35.3147248276, 3)
q_divisions = 60  # number of runs, set to 1 if you want to generate single event based on q
adjust_n_rating = True  # this adjusts the  n value dependent on the discharge, input a b and trend params (log recommended)
a = [-0.0054592532, -0.0043528493]
b = [0.0388453234, 0.0473590563]
n_regions = ['Channel', 'Structures']
function_type = ['log', 'log']  # linear, log, exp, power, hyper  (note x is metric)
max_n = [0.15, 0.15]
min_n = [0.025, 0.035]

# Settings for sim event
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
us_bc = 'Upstream BC'
ds_bc = 'Downstream BC'
verbose = True

# TODO:
# add datetime range start to config, or pull from hecras?
# option on grab hydrograph from file and will adjust time params autmatically