from pathlib import Path


# calibration config file
hec_version = '66'

cal_observed = False
cal_indirect = True
cal_EG_slope = True
gen_ratecurv = False
sim_event = False

batch_process = False
create_i0_simplex = True #only works for Nelder-Mead
algorythm = 'Nelder-Mead'  # 'Nelder-Mead' 'SCE-UA'
objective_function = 'RMSE'  # 'RMSE' 'MAE

structures = False  # will assign channel n to structures in cal_observed (currently assigns channel n to structure)
independent_structures = False  # calibrates all structures seperatly from channel input to simplex same as Q  (structures must be true)
EPSG = 'EPSG:6514'  # EPSG:6514 (NAD83 2011m MT state plane), EPSG:5703 (NAVD88 height m) use geiod2018
find_cell_index = False  # will get cell index from WSP coordinates and update csv. Must Have Unique id in ID field!
get_inst_q = False  # will grab current reporting discharge for gauge, will grab MaxQ if False
export_shapefile = False  # for gen_ratecurve & sim_event, will save last inundation shapefile to Directory
export_geojsons = False  # for gen_ratecurve & sim_event, will save all inundation GeoJSON's to Directory (export shape must be True)

# define directories
Directory = Path(r'C:\Users\CND641\Documents\76F 04900 Monture Creek nr Ovando\HECRAS')
ras_directory = Directory.joinpath('RAS_files')
gis_directory = Directory.joinpath('GIS')
geojson_directory = Directory.joinpath('GIS', 'GeoJSONs')
input_directory = Directory.joinpath('Input')
output_directory = Directory.joinpath('Output')

# define relevant file paths, calibration parameters, and define channel centerline
prj = 'MontureCreek'
prj_filename = ras_directory.joinpath(f'{prj}.prj')
ghdf_filename = ras_directory.joinpath(f'{prj}.g04.hdf')
phdf_filename = ras_directory.joinpath(f'{prj}.p02.hdf')
geom_filename = ras_directory.joinpath(f'{prj}.g04')
flow_filename = ras_directory.joinpath(f'{prj}.u03')
plan_filename = ras_directory.joinpath(f'{prj}.p02')
lchdf_filename = ras_directory.joinpath('Land Classification', 'LandCover.hdf')

grid_filename = gis_directory.joinpath('flow_area.shp')  # for finding cell only?
# Cntrln_filename = Path(f'{gis_directory}/centerline.shp')  # depriciated
terrain_raster = gis_directory.joinpath('Terrain (3).Clone.tif')  # just a template for expoerting wse's
wse_filename = input_directory.joinpath('hwms.csv')
trendline = input_directory.joinpath('trendline.csv')
q_list = input_directory.joinpath('Q_list.csv')

# Output filepaths
simplex_filename = output_directory.joinpath('simplex_dataframe.csv')
iterations_filename = output_directory.joinpath('model_iterations.csv')
wse_prof_filename = output_directory.joinpath('wse_profiles_output.csv')
rating_curve_filename = output_directory.joinpath('rating_curve.csv')
batch_filename = output_directory.joinpath('batch_results.csv')

set_friction_slope = True  # overrides friction slopes prior to initial run
FS_params = ['ds_fs']  # can use one or both for cal_EG_slope, us_fs must be first if both
friction_slope = [0.0042]

# define mannings values per region
Man_n_params = ['UpstreamChannel', 'DownstreamChannel']  # eg. 'Grassland', 'Road', 'NoData', 'Channel', 'Riparian'
Man_n_vals = [0.035, 0.032]

Q_params = ['Upstream BC']  # discharge is last in bounds/ initial guess
Q_params_cfs = 550
Q_params_vals = [round(Q_params_cfs * 0.02832, 3)]

# (us_fs, ds_fs, landcover_regions, structures, discharge)
bounds = [(0.0035, 0.0050), (0.01, 0.08),(0.01, 0.08), (11.0, 25.0)]
i0_guess = [(0.0040, 0.0042),(0.03, 0.035), (0.03, 0.035), (18.0, 20.0)]
max_runs = 250

gauge_el_NAVD88m = 1196.158  # site specific (977.35 is bridge low chord)

# Settings for rating curve gen
use_Q_list = True  # this uses a csv list of discharges from inputs rather than generating its own
min_cfs = 0
min_q = round(min_cfs * 0.02832, 3)
max_cfs = 420  # also used for sim event
max_q = round(max_cfs * 0.02832, 3)
q_divisions = 60  # number of runs, set to 1 if you want to generate single event based on q
adjust_n_rating = True  # this adjusts the  n value dependent on the discharge, input a b and trend params (log recommended)
a = [-0.011779]
b = [0.071445]
n_regions = ['Channel']
function_type = ['log']  # linear, log, exp, power, hyper  (note x is metric)
max_n = [0.14]
min_n = [0.02]

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
