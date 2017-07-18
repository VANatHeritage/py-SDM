# ----------------------------------------------------------------------------------------
# raster_fill.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017-07-18
# Last Edit: 2017-07-18
# Creator(s): David Bucklin

# Summary:
# Fills in missing (nodata) cells in a raster, using information from
# surrounding cells (Focal Statistics)

# Usage Tips:
# Set all paths prior to usage.

# Dependencies:
# Spatial analyst, numpy

# Syntax:  
# [need to manually enter options, paths and run entire script in IDE]
# ----------------------------------------------------------------------------------------

# import libs
import arcpy
import numpy as np
import numpy.ma as ma
from arcpy import env
from arcpy.sa import *

# options
# focal stats fill type? ('MEAN','MAJORITY','MEDIAN')
typ = 'MEAN'
# run recursively (1km fill at a time) or with one focal stats (with minimum necessary radius to fill all nodata)
recursive = False

# set paths
# output file
out_file = 'E:/arcmap_wd/VA_SDM_SSURGO/ssurgoClay_fullrad.tif'
# scratch working dir
wd = 'E:/arcmap_wd/scratch_folder/'
# initial raster file, with nodata gaps to fill
lyr = 'E:/r_wd/ssurgo_clay.tif'
# a template raster file, to mask, set extent, and get pixel size
template = 'E:/r_wd/distcaco3.tif'
# clipping region shapefile (for initial data processing subset)
clip = 'E:/r_wd/sdmVA_pred_area.shp'
# end set paths

# set environmental variables
arcpy.env.workspace = wd
arcpy.env.snapRaster = template
arcpy.env.extent = template
arcpy.env.overwriteOutput = True

# convert inraster to numpy array, set nodata values to -9999  
npArray = arcpy.RasterToNumPyArray(template,"","","",-9999)
# mask the non-nodata values, and take them out by compressing  
ndtempl = len(ma.masked_where(npArray <> -9999, npArray).compressed())
ndfinal = 0

# process data
desc = arcpy.Describe(template)  
cellsize = desc.children[0].meanCellHeight  

r1 = arcpy.Resample_management(lyr, wd + "r1.tif", str(cellsize), "BILINEAR")
r2 = arcpy.Clip_management(r1, "#", wd + "r2.tif", clip, "#", "ClippingGeometry")

if not recursive:
	# check out Spatial Analyst for EucDistance
	arcpy.CheckOutExtension("Spatial")

	# retrieve maximum distance of nodata value to real values
	# for conditionally filling nodata values with mean of circular neighborhood (with radius mx)
	ed1 = EucDistance(r2)
	ed2 = ExtractByMask(ed1, template)
	maxd = arcpy.GetRasterProperties_management(ed2, "MAXIMUM")
	mx = maxd.getOutput(0) + 90
	# the +90 ensures that all pixels should get more than one pixel of real data in their focal window
	print 'Radius size: ' + str(mx) + ' m'

	# this would fill in nodata cells the mean in a focal neighborhood with a radius equal to the max distance from 
	# a nodata cell to a real value. It's very slow with large radius values (e.g, 5 km+)
	r3 = Con(IsNull(r2),FocalStatistics(r2, NbrCircle(mx, 'MAP'),typ), r2)
	r3 = ExtractByMask(r3, template)
	r3.save(out_file)

else:
	# this loop recursively fills nodata cells within 1km until the number of nodata cells matches the template dataset
	while ndfinal != ndtempl:
		r2 = Con(IsNull(r2),FocalStatistics(r2, NbrCircle(1000, 'MAP'),typ), r2)
		r2 = ExtractByMask(r2, template)
		npArray = arcpy.RasterToNumPyArray(r2,"","","",-9999)
		ndfinal = len(ma.masked_where(npArray <> -9999, npArray).compressed())
		print ndfinal
		print ndtempl

	## DON'T FORGET TO SAVE!!
	r2.save(out_file)
