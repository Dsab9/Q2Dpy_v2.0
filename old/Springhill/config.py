from pathlib import Path


# calibration config file
hec_version = '641'

cal_observed = False
cal_indirect = False
gen_hydrograph = True
sim_event = False

structures = False  # will assign channel n to structures in cal_indirect
EPSG = 'EPSG:6514'  # EPSG:6514 (NAD83 2011m MT state plane), EPSG:5703 (NAVD88 height m) use geiod2018
find_cell_index = False  # will get cell index from WSP coordinates and update csv
get_inst_q = False  # will grab current reporting discharge for gauge, will grab MaxQ if False
export_shapefile = True  # for gen_hydrograph & sim_event, will save last inundation shapefile to Directory
export_geojsons = True  # for gen_hydrograph & sim_event, will save all inundation GeoJSON's to Directory (export shape must be True)

# define directories
Directory = Path(r'S:\Water_Management\Site Models\41O 03000 Teton abv Springhill\HECRAS')
ras_directory = Path(f'{Directory}/RAS_files')
gis_directory = Path(f'{Directory}/GIS')
geojson_directory = Path(f'{Directory}/GIS/GeoJSONs')
input_directory = Path(f'{Directory}/Input')
output_directory = Path(f'{Directory}/Output')

# define relevant file paths, calibration parameters, and define channel centerline
prj_filename = Path(f'{ras_directory}/Springhill_lrg.prj')
ghdf_filename = Path(f'{ras_directory}/Springhill_lrg.g01.hdf')
phdf_filename = Path(f'{ras_directory}/Springhill_lrg.p03.hdf')
flow_filename = Path(f'{ras_directory}/Springhill_lrg.u03')
plan_filename = Path(f'{ras_directory}/Springhill_lrg.p03')
lchdf_filename = Path(f'{ras_directory}/Land Classification/LandCover.hdf')

grid_filename = Path(f'{gis_directory}/flow_area.shp')
Cntrln_filename = Path(f'{gis_directory}/centerline.shp')
terrain_raster = Path(f'{gis_directory}/ras_terrain.tif')
WSP_filename = Path(f'{input_directory}/channel_cal.csv')

# Output filepaths
simplex_filename = Path(f'{output_directory}/simplex_dataframe.csv')
iterations_filename = Path(f'{output_directory}/model_iterations.csv')
wse_prof_filename = Path(f'{output_directory}/wse_profiles_output.csv')
rating_curve_filename = Path(f'{output_directory}/rating_curve.csv')

# define mannings values per region
Man_n_params = ['Channel']  # 'Grassland', 'Road', 'NoData', 'Channel', 'Riparian'
Man_n_vals = [0.45]

Q_params = ['UpstreamBC']  # discharge is last in bounds/ initial guess
Q_params_vals = [0.953]

bounds = [(0.01, 0.9)]
i0_guess = [(0.04, 0.05)]
max_runs = 70

# rating curve gen info
use_Q_list = True

min_cfs = 0
min_q = round(min_cfs * 0.02832, 3)
max_cfs = 80  #6970 is max
max_q = round(max_cfs * 0.02832, 3)
q_divisions = 4  # number of runs, set to 1 if you want to generate single event based on q
gauge_el_NAVD88m = 1237.620  # site specific

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

# TODO:
# add datetime range start to config, or pull from hecras?
# currently, Q for channel cal needs to be set manually, script it to take q_params and adjust

