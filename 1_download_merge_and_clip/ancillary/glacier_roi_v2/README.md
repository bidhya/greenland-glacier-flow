
# MEaSUREs Glacier ROIs v2
**Tom Chudley | 2022-02-23**

This directory contains version 2 of the glacier ROI extents, stored in version 1 form at `/fs/project/howat.4/sentinel2/ancillary/glaciers_roi_proj.shp`. 

## Motivation

The motivation for regridding these extents is to allow Sentinel-2 and Landsat data to be reprojected onto a grid of identical boundaries (either as a preprocessing or postprocessing step), whilst minimising the number of reprojection steps required. The version 1 ROI extents were designed around Landsat use, leading to ROI extents based around 15 m or 30 m grid sizes. This meant that velocity datasets (100 m or 300 m resolution) and Sentinel-2 datasets (10 m resolution) had to be resampled onto this extent, leading to inconsistent gridding/boundaries/grid size depending on the software used to do so.

## Changes

The new ROI extents retain the v1 origin. This is the origin in the GeoTiff sense (the top left (xmin, ymax) point), to allow for some compatibility with the old version. 

The new height and widths of the ROIs are rounded up to the nearest 300 m. This gives the total heights and widths with factors of 300, 100, 30, 15, and 10 metres, allowing for Landsat and Sentinel-2 raw data (15, 30, 10 m) as well as velocity datasets (100 m and 300 m) to be gridded onto the same total bounds.

# Files

The directory contains the new ROI as a geopackage (`glaciers_roi_proj_v2_300m.gpkg`) and shapefile (`glaciers_roi_proj_v2_300m.shp` + ancillery files).

## Appendix 1

Python code used to calculate new ROIs from original.

```python
import geopandas as gpd
import numpy as np
from shapely.geometry import box

# read original shapefile as Geopandas dataframe
gdf = gpd.read_file("/fs/project/howat.4/sentinel2/ancillary/glaciers_roi_proj.shp")

# create Pandas dataframe of xmin, xmax, ymin, ymax
df = gdf.bounds

# rename these columns *_orig
df.columns = [x+"_orig" for x in df.columns]

# insert 'region' ID column as first column
df.insert(0, "region", gdf.region)

# Work out decimal multiple of 300 m of the original ROI
df["width_300m_px"] = (df["maxx_orig"] - df["minx_orig"]) / 300
df["height_300m_px"] = (df["maxy_orig"] - df["miny_orig"]) / 300

# Round up to nearest int multiple of 300 m
df["width_300m_px_round"] = np.ceil(df["width_300m_px"])
df["height_300m_px_round"] = np.ceil(df["height_300m_px"])

# Work out new maxx and miny from this origin
df["maxy_new"] = df["maxy_orig"]
df["minx_new"] = df["minx_orig"]
df["miny_new"] = df["maxy_orig"] - ( df["height_300m_px_round"] * 300 )
df["maxx_new"] = df["minx_orig"] + ( df["width_300m_px_round"] * 300 )

# create new geometries as Shapely polygons
geometries=[]
for _, row in df.iterrows():
    geom = box( row["minx_new"], row["miny_new"], row["maxx_new"], row["maxy_new"] )
    geometries.append(geom)

# Create new geopandas dataframe
gdf_new = gpd.GeoDataFrame({"region": df.region}, geometry=geometries, crs="EPSG:3413")

gdf_new.to_file("glaciers_roi_proj_v2_300m.shp")
gdf_new.to_file("glaciers_roi_proj_v2_300m.gpkg", layer='roi', driver="GPKG")
```