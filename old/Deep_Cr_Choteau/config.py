from pathlib import Path


# calibration config file
hec_version = '641'

cal_observed = False
cal_indirect = False
cal_EG_slope = False
gen_ratecurv = True
sim_event = False

structures = False  # will assign channel n to structures in cal_observed (currently assigns channel n to structure)
EPSG = 'EPSG:6514'  # EPSG:6514 (NAD83 2011m MT state plane), EPSG:5703 (NAVD88 height m) use geiod2018
find_cell_index = False  # will get cell index from WSP coordinates and update csv
get_inst_q = False  # will grab current reporting discharge for gauge, will grab MaxQ if False
export_shapefile = True  # for gen_ratecurve & sim_event, will save last inundation shapefile to Directory
export_geojsons = True  # for gen_ratecurve & sim_event, will save all inundation GeoJSON's to Directory (export shape must be True)

# define directories
Directory = Path(r'S:\Water_Management\Site Models\41O 04850 Deep Creek near Choteau\HECRAS')
ras_directory = Path(f'{Directory}/RAS_files')
gis_directory = Path(f'{Directory}/GIS')
geojson_directory = Path(f'{Directory}/GIS/GeoJSONs')
input_directory = Path(f'{Directory}/Input')
output_directory = Path(f'{Directory}/Output')

# define relevant file paths, calibration parameters, and define channel centerline
prj_filename = Path(f'{ras_directory}/Deep_Creek_Choteau.prj')
ghdf_filename = Path(f'{ras_directory}/Deep_Creek_Choteau.g04.hdf')
phdf_filename = Path(f'{ras_directory}/Deep_Creek_Choteau.p02.hdf')
flow_filename = Path(f'{ras_directory}/Deep_Creek_Choteau.u02')
plan_filename = Path(f'{ras_directory}/Deep_Creek_Choteau.p02')
lchdf_filename = Path(f'{ras_directory}/Land Classification/LandCover.hdf')

grid_filename = Path(f'{gis_directory}/flow_area.shp')  # for finding cell only?
# Cntrln_filename = Path(f'{gis_directory}/centerline.shp')  # depriciated
terrain_raster = Path(f'{gis_directory}/Final_Terrain.tif')  # just a template for expoerting wse's
wse_filename = Path(f'{input_directory}/channel_cal.csv')  # indirect only

# Output filepaths
simplex_filename = Path(f'{output_directory}/simplex_dataframe.csv')
iterations_filename = Path(f'{output_directory}/model_iterations.csv')
wse_prof_filename = Path(f'{output_directory}/wse_profiles_output.csv')
rating_curve_filename = Path(f'{output_directory}/rating_curve.csv')

FS_params = ['us_fs', 'ds_fs']  # can use one or both for cal_EG_slope
set_friction_slope = False  # overrides friction slopes prior to initial run
upstream_friction_slope = 0.003
downstream_friction_slope = 0.0025

# define mannings values per region
Man_n_params = ['Channel']  # 'Grassland', 'Road', 'NoData', 'Channel', 'Riparian'
Man_n_vals = [0.051]

Q_params = ['UpstreamBC']  # discharge is last in bounds/ initial guess
Q_params_cfs = 68.12
Q_params_vals = [round(Q_params_cfs * 0.02832, 3)]

bounds = [(0.03, 0.07)]
i0_guess = [(0.05, 0.052)]
max_runs = 70

gauge_el_NAVD88m = 1252.197  # site specific

# rating curve gen info
use_Q_list = True  # this uses a csv list of discharges from inputs rather than generating its own
min_cfs = 0
min_q = round(min_cfs * 0.02832, 3)
max_cfs = 420  # also used for sim event
max_q = round(max_cfs * 0.02832, 3)
q_divisions = 60  # number of runs, set to 1 if you want to generate single event based on q


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
perimeter = 'Perimeter00'
us_bc = 'UpstreamBC'
ds_bc = 'DownstreamBC'
verbose = True

# TODO:
# add a q-input in the channel cal setup
# Potential problem if more than one channel classification, should work with unique names?
# add datetime range start to config, or pull from hecras?
# currently, Q for channel cal needs to be set manually, script it to take q_params and adjust
# option on grab hydrograph from file and will adjust time params autmatically

