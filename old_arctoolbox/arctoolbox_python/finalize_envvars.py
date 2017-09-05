# ----------------------------------------------------------------------------------------
# finalize_envvars.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2017
# Last Edit: 2017-08-16
# Creator(s): David Bucklin

# Summary:
# Takes a raster and optional template raster,
# and a multiplier, and returns an integer raster
# with [value] * multplier

# Dependencies:
# Spatial analyst

# Syntax:  
# finalize_envvars.py(in_rast, mult, out_rast, [mask])
# ----------------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *

# in raster
in_rast = arcpy.GetParameterAsText(0)

# multiplier
mult = arcpy.GetParameterAsText(1)

# output gdb
out_rast = arcpy.GetParameterAsText(2)

# optional mask
mask = arcpy.GetParameterAsText(3)

mult = int(mult)

if mask:
   arcpy.env.snapRaster = mask
   in_rast = ExtractByMask(in_rast,mask)

out = Int(Plus(Times((in_rast),mult),.5001))

out.save(out_rast)