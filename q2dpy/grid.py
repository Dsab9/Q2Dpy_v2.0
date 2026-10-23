"""Grid / mesh helpers."""
import geopandas as gpd
import pandas as pd


def get_cell_index(grid_filename, wse_filename):
    """Finds the 2D mesh cell containing each observation point (Easting/Northing)
    and writes it to the 'Cell_Index' column of the observation csv."""
    fa_gdf = gpd.read_file(grid_filename)
    # projection of the cell grid
    crs = fa_gdf.crs

    in_df = pd.read_csv(wse_filename)
    pts_array = gpd.points_from_xy(in_df['Easting'], in_df['Northing'], crs=crs)
    pts_gdf = gpd.GeoDataFrame(in_df, geometry=pts_array, crs=crs)
    overlay = fa_gdf.overlay(pts_gdf, how='intersection', keep_geom_type=False)
    cell_col = [col for col in overlay if col.startswith('Cell')][0]

    for index, row in in_df.iterrows():
        match = overlay.loc[overlay['ID'] == row['ID'], cell_col]
        if match.empty:
            raise ValueError(f"Point ID {row['ID']} does not fall inside any mesh cell in {grid_filename}")
        in_df.at[index, 'Cell_Index'] = int(match.values[0])

    try:
        in_df = in_df.drop(columns='geometry')
    except KeyError:
        pass
    in_df.to_csv(wse_filename, index=False)
    print("Cell Index Updated")