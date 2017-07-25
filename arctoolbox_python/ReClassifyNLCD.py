# ----------------------------------------------------------------------------------------
# nlcd_summaries.py
# Version:  ArcGIS 10.3.1 / Python 2.7.8
# Creation Date: 2016
# Last Edit: 2017-07-25
# Creator(s): Amy Conley, David Bucklin

# Summary:
# Takes NLCD (including impervious and canopy coverage) data,
# a study region, and a raster mask, and outputs 
# summary variables for land cover types, using 
# neighborhood analysis, in a 3x3 window, 10-cell circle,
# and 100-cell circle around the focal cell

# Usage Tips:
# Set all paths prior to usage.

# Dependencies:
# Spatial analyst

# Syntax:  
# ReClassifyNLCD.py(out_gdb, project_nm, extent_shp, nlcd_classified, impervious_raster, canopy_raster, {mask})
# ----------------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *

# begin variables

# output gdb
out_gdb = arcpy.GetParameterAsText(0)

# file name prefix for outputs
project_nm = arcpy.GetParameterAsText(1)

# study extent 
extent_shp = arcpy.GetParameterAsText(2)

# input raster(s)
nlcd_classified=arcpy.GetParameterAsText(3)
impervious_raster=arcpy.GetParameterAsText(4)
canopy_raster=arcpy.GetParameterAsText(5)

# optional mask
mask = arcpy.GetParameterAsText(6)

# end variables

# set environmental variables
arcpy.CheckOutExtension("Spatial")
arcpy.env.workspace = out_gdb
arcpy.env.overwriteOutput=True

# mask default
if mask:
   arcpy.AddMessage("Using specified mask")
else:
   arcpy.Clip_management(nlcd_classified,"#","maskfinal", extent_shp, "#", "ClippingGeometry")
   mask=SetNull("maskfinal","maskfinal","Value = 0")
   mask.save("maskfinal")

arcpy.env.snapRaster = mask

# buffer extent feature
extent_shp = arcpy.Buffer_analysis(in_features=extent_shp, out_feature_class="nlcdprocextent", buffer_distance_or_field="5000 Meters", dissolve_option="ALL")

# clean (clip and set null) rasters
# nlcd classified
in_nlcd = arcpy.Clip_management(nlcd_classified,"#","nlcd_cliptemp", extent_shp, "#", "ClippingGeometry")
inraster= "nlcd_cliptemp"
where_clause="Value = 0"
output_raster="nlcd_classified_clean"
outsetNull=SetNull(inraster,inraster,where_clause)
outsetNull.save(output_raster)
in_nlcd_class="nlcd_classified_clean"

# impervious
output_raster="nlcd_impervious_clean"
outsetNull=ExtractByMask(impervious_raster,in_nlcd_class)
outsetNull=SetNull(outsetNull,outsetNull,"Value = 127")
outsetNull.save(output_raster)
in_impervious="nlcd_impervious_clean"

# canopy
output_raster="nlcd_canopy_clean"
outsetNull=ExtractByMask(canopy_raster,in_nlcd_class)
outsetNull.save(output_raster)
in_canopy="nlcd_canopy_clean"


##Step 0: Set up the Remap Values

#Raster values and their associated habitat in the NLCD
#11= Open Water
#12= Perennial Ice/Snow
#21= Developed Open Space
#22= Developed Low Intensity
#23= Developed Medium Intensity
#24=Developed High Intensity
#31 = Barren Land
#41 = Deciduous Forest
#42 = Evergreen Forest
#43 = Mixed Forest
#52=Shrub/Scrub
#71=Grassland/Herbaceous
#81=Pasture/Hay
#82=Cultivated Crops
#90= Woody Wetlands
#95= Emergent Herbaceous Wetlands


#For Forest we only want values 41,42,43
remap_forest=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[24,0],[31,0],[41,1],[42,1],[43,1],[52,0],[71,0],[81,0],[82,0],[90,0],[95,0]])

#For Wetland we only want 90 and 95
remap_wetland=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[24,0],[31,0],[41,0],[42,0],[43,0],[52,0],[71,0],[81,0],[82,0],[90,1],[95,1]])

#For Open Area we want 31, 71,81,82
remap_Open=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[24,0],[31,1],[41,0],[42,0],[43,0],[52,0],[71,1],[81,1],[82,1],[90,0],[95,0]])

#For Water we want 11
remap_water=RemapValue([[11,1],[12,0],[21,0],[22,0],[23,0],[24,0],[31,0],[41,0],[42,0],[43,0],[52,0],[71,0],[81,0],[82,0],[90,0],[95,0]])

#For ShrubScrub we want 52
remap_ShrubScrub=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[24,0],[31,0],[41,0],[42,0],[43,0],[52,1],[71,0],[81,0],[82,0],[90,0],[95,0]])

#For ConiferForest we want 42
remap_evergreen=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[24,0],[31,0],[41,0],[42,1],[43,0],[52,0],[71,0],[81,0],[82,0],[90,0],[95,0]])

#For Deciduous/Mix we want 41 and 43 and we want 43 half as much so 41->100 and 43->50
remap_decidmix=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[24,0],[31,0],[41,100],[42,0],[43,50],[52,0],[71,0],[81,0],[82,0],[90,0],[95,0]])

#For Evergreen/Mix we want 42 and 43 and we want 43 half as much so 42->100 and 43->50
remap_evermix=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[24,0],[31,0],[41,0],[42,100],[43,50],[52,0],[71,0],[81,0],[82,0],[90,0],[95,0]])

# do reclassifys
inraster= in_nlcd_class

#Step 2 - Reclass the rasters for each desired land type
reclass_field= "Value"
out_reclassify_forest=Reclassify(inraster,reclass_field,remap_forest,"NODATA")
out_reclassify_forest.save(project_nm + "_b_forest_n")

out_reclassify_wetland=Reclassify(inraster,reclass_field,remap_wetland,"NODATA")
out_reclassify_wetland.save(project_nm + "_b_wetland_n")

out_reclassify_open=Reclassify(inraster,reclass_field,remap_Open,"NODATA")
out_reclassify_open.save(project_nm + "_b_open_n")

out_reclassify_water=Reclassify(inraster,reclass_field,remap_water,"NODATA")
out_reclassify_water.save(project_nm + "_b_water_n")

out_reclassify_ShrubScrub=Reclassify(inraster,reclass_field,remap_ShrubScrub,"NODATA")
out_reclassify_ShrubScrub.save(project_nm + "_b_shrubscrub_n")

#########Added 2017 - Split the forest into evergreen/mixed forest and deciduous/mixed forest

out_reclassify_Evergreen=Reclassify(inraster,reclass_field,remap_evergreen,"NODATA")
out_reclassify_Evergreen.save(project_nm + "_b_evergreen_n")

out_reclassify_decidmix=Reclassify(inraster,reclass_field,remap_decidmix,"NODATA")
out_reclassify_decidmix.save(project_nm + "_b_decidmix_n")

out_reclassify_Evermix=Reclassify(inraster,reclass_field,remap_evermix,"NODATA")
out_reclassify_Evermix.save(project_nm + "_b_evermix_n")

print "done reclassifying"
#Step 3: Calculate focal statistics

# get list of binary rasters and add impervious and canopy to it
proj_source=arcpy.ListRasters(project_nm  + "_b_*")
proj_source.append(in_impervious)
proj_source.append(in_canopy)

neighborhood_1=NbrRectangle(3,3,"CELL")
neighborhood_10=NbrCircle(10,"CELL")
neighborhood_100=NbrCircle(100,"CELL")

for raster in proj_source:
    if "forest" in raster:
        basename="mean_forest"
    elif "wetland" in raster:
        basename="mean_wetland"
    elif "open" in raster:
        basename="mean_open"
    elif "water" in raster:
        basename="mean_water"
    elif "shrubscrub" in raster:
        basename="mean_shrubscrub"
    elif "canopy" in raster:
        basename="mean_canopy_n"
    elif "impervious" in raster:
        basename="mean_impervious_n"
    elif "evergreen" in raster:
        basename="mean_evergreen_n"
    elif "decidmix" in raster:
        basename="mean_deciduous_mixed_n"
    elif "evermix" in raster:
        basename="mean_evergreen_mixed_n"
    else:
        continue
    
    print "Preparing to calculate focal statistics for "+basename

    out_raster_1=project_nm + "_" + basename+"_1"
    out_raster_10=project_nm + "_" + basename+"_10"
    out_raster_100=project_nm + "_" + basename+"_100"
    print "Calculating neighborhood 1 cell square"
    outFocal_1=FocalStatistics(raster,neighborhood_1,"MEAN","DATA")
    outFocal_1=Con(IsNull(outFocal_1),0, outFocal_1)
    outFocal_1=ExtractByMask(outFocal_1,"maskfinal")
    outFocal_1.save(out_raster_1)
    print "Finished with first neighborhood"
    print "Calculating neighborhood 10 cell circle"
    outFocal_10=FocalStatistics(raster,neighborhood_10,"MEAN","DATA")
    outFocal_10=Con(IsNull(outFocal_10),0, outFocal_10)
    outFocal_10=ExtractByMask(outFocal_10,"maskfinal")
    outFocal_10.save(out_raster_10)
    print "Finished with second neighborhood"
    print "Calculating neighborhood 100 cell circle"
    outFocal_100=FocalStatistics(raster,neighborhood_100,"MEAN","DATA")
    outFocal_100=Con(IsNull(outFocal_100),0, outFocal_100)
    outFocal_100=ExtractByMask(outFocal_100,"maskfinal")
    outFocal_100.save(out_raster_100)
    print "Finished with "+basename
    
## clean up
if arcpy.Exists("maskfinal"):
    arcpy.Delete_management("maskfinal")
arcpy.Delete_management("nlcdprocextent")
arcpy.Delete_management("nlcd_cliptemp")