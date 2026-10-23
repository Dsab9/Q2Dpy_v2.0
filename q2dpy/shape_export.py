"""Module creates a shapefile or geojson of inundated area from output wse raster"""

import geopandas as gpd
import pandas as pd
import rasterio as rio
from osgeo import gdal
from osgeo.gdalconst import GA_Update
from rasterio import features, enums
from shapely import geometry

import config
from model import HecRas


# import json

# function needs terrain raster and flow area grid in gis directory
def export_shapefile():
    """creates an inundation area shapefile given the wse raster output from RAS and the terrain raster"""
    # this outputs wse of all cells for last iteration
    if config.verbose is True:
        print("Exporting results...")
    working_folder = config.gis_directory
    EPSG = config.EPSG

    hecmodel = HecRas(config.prj_filename, config.ghdf_filename, config.phdf_filename, config.flow_filename,
                      config.plan_filename, config.lchdf_filename)
    # print("Importing RAS results...")
    result = hecmodel.load_current_plan_results(config.phdf_filename)
    result = result[-1]
    wse_df = pd.DataFrame(result)
    wse_df = wse_df.rename(columns={0: 'WSE'})
    wse_df['CellIndex'] = wse_df.index
    # df.to_csv(r"G:\WATER_MG\HEC-RAS\SpringHill_41O03000\SpringHill_lrg\gis\wse.csv")

    #  Joins cell wse to cell shapefile (geodataframe)
    # print("Joining RAS results to model grid...")
    fa_gdf = gpd.read_file(config.grid_filename)
    wse_gdf = fa_gdf.merge(wse_df, on='CellIndex', how='left')
    # wse_gdf.to_file(f"{working_folder}/merged_wse.shp")

    # gets list of geometries and creates tuples of geometry value pairs, value is the attribute value you want to burn
    geom = [shapes for shapes in wse_gdf.geometry]
    geom_value = ((geom, value) for geom, value in zip(wse_gdf.geometry, wse_gdf['WSE']))

    #  Reads template raster, rasterizes wse shapefile
    # print("Generating WSE raster...")
    raster_temp = rio.open(config.terrain_raster)
    raster_wse = features.rasterize(geom_value,
                                    out_shape=raster_temp.shape,
                                    transform=raster_temp.transform,
                                    all_touched=True,
                                    fill=0,  # background value
                                    merge_alg=enums.MergeAlg.replace,
                                    dtype=rio.float32)

    # Reads terrain raster (use same raster as template)
    with rio.open(config.terrain_raster) as ras1:
        raster_surface = ras1.read(1)

    raster_dif = raster_wse - raster_surface
    raster_dif[raster_dif <= 0.01] = 0
    raster_dif[raster_dif == 9999] = 0

    # writes raster as a .tif
    # print("Writing WSE raster as tif...")
    with rio.open(
            f"{working_folder}/rasterized_vector.tif", "w",
            driver="GTiff",
            crs=raster_temp.crs,
            transform=raster_temp.transform,
            dtype=rio.float32,
            count=1,
            width=raster_temp.width,
            height=raster_temp.height) as dst:
        dst.write(raster_dif, indexes=1)

    # This sets zero value to no data and re-saves tif
    filename = f"{working_folder}/rasterized_vector.tif"
    nodata = 0
    # open the file for editing
    ras = gdal.Open(filename, GA_Update)
    # loop through the image bands
    for i in range(1, ras.RasterCount + 1):
        # set the nodata value of the band
        ras.GetRasterBand(i).SetNoDataValue(nodata)
    # unlink the file object and save the results
    ras = None

    # print("Vectorizing raster...")
    with rio.open(f"{working_folder}/rasterized_vector.tif") as src:
        data = src.read(1, masked=True)
        # Use a generator instead of a list
        shape_gen = ((geometry.shape(s), v) for s, v in features.shapes(data, transform=src.transform))
        # builds gdf and exports to shp
        df = pd.DataFrame(shape_gen, columns=['geometry', 'class'])
        gdf = gpd.GeoDataFrame(data=df["class"], geometry=df.geometry, crs=EPSG)

        # print("Merging vector shapes...")
        gdf_merged = gdf.dissolve().explode(index_parts=True)

        # import libpysal  # More efficient way?
        # # create spatial weights matrix
        # W = libpysal.weights.Queen.from_dataframe(gdf)
        # # get component labels
        # components = W.component_labels
        # combined_polygons = gdf.dissolve(by=components)

        # print("Removing the fuzz...")
        # Removes everything 3m^2 or less
        mask = gdf_merged.area > 3
        remaining = gdf_merged.loc[mask]
        remaining.to_file(f"{working_folder}/inundation.shp", driver='ESRI Shapefile')
        # print("Inundation shapefile successfully saved")


def saveas_geojson(stage):
    """converts the shapefile to a geojson"""
    stage = str(round(stage, 2))
    shpfile = gpd.read_file(f'{config.gis_directory}/inundation.shp')
    new_shpfile = shpfile.to_crs('epsg:4326')
    new_shpfile.to_file(f'{config.geojson_directory}/{stage}.geojson', driver='GeoJSON')
    print(f"shapefile saved as '{stage}.geojson'")

# export_shapefile()
