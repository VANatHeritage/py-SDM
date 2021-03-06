import arcpy


class Toolbox(object):
   def __init__(self):
      self.label = "Environmental variables processing"
      self.alias = "envvarproc"

      # List of tool classes associated with this toolbox (defined classes below)
      self.tools = [finalizeEnvVar, rasterFill, reclassNLCD, reclassCCAP]

# finalize environmental variables
class finalizeEnvVar(object):
   def __init__(self):
      self.label = "Finalize Environmental Variables"
      self.description ="Takes input raster, an optional a raster mask, " + \
                        "and a multiplier. Values are multiplied by the " + \
                        "multiplier and the raster is converted to integer. " + \
                        "The raster is also masked and extended/cropped to " + \
                        "the mask extent if a mask is provided."
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      in_rast = arcpy.Parameter(
            displayName="Input Raster",
            name="in_rast",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")
      
      mult = arcpy.Parameter(
            displayName="Multiplier",
            name="mult",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
      
      mask = arcpy.Parameter(
            displayName="Mask",
            name="mask",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")
      
      out_rast = arcpy.Parameter(
            displayName = "Output Raster",
            name="out_rast",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Output")
      
      params = [in_rast,mult,mask,out_rast]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      try:
         if arcpy.CheckExtension("Spatial") != "Available":
            raise Exception
      except Exception:
         return False  # tool cannot be executed

      return True  # tool can be executed

   def updateParameters(self, params):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""

      from arcpy.sa import *
      from arcpy import env

      # in raster
      in_rast = params[0].valueAsText

      # multiplier
      mult = params[1].valueAsText

      # optional mask
      mask = params[2].valueAsText
      
      # output raster
      out_rast = params[3].valueAsText

      mult = int(mult)

      if mask:
         arcpy.env.extent = mask
         arcpy.env.snapRaster = mask
         in_rast = ExtractByMask(in_rast,mask)

      out = Int(Plus(Times((in_rast),mult),.5001))

      out.save(out_rast)

      return


# fill noData in rasters
class rasterFill(object):
   def __init__(self):
      self.label = "Fill NoData areas in Raster"
      self.description ="Fills in missing (nodata) cells in a raster, using information from surrounding cells (Focal Statistics)"
      self.canRunInBackground = True
      #self.category
      #self.stylesheet

   def getParameterInfo(self):
      """Define parameter definitions"""
      lyr = arcpy.Parameter(
            displayName="Input Raster",
            name="lyr",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")
      
      wd = arcpy.Parameter(
            displayName="Working/scratch directory",
            name="wd",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
      
      template = arcpy.Parameter(
            displayName="Template raster",
            name="template",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")
      
      clip = arcpy.Parameter(
            displayName = "Processing area (clip features)",
            name="clip",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
      
      out_file = arcpy.Parameter(
            displayName = "Output raster",
            name = "out_file",
            datatype = "DERasterDataset",
            parameterType = "Required",
            direction = "Output")
            
      typ = arcpy.Parameter(
            displayName = "Focal statistic",
            name = "typ",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      typ.filter.type = "ValueList"
      typ.filter.list = ['MEAN','MAJORITY','MEDIAN','MAXIMUM','MINIMUM']
      
      recursive = arcpy.Parameter(
            displayName = "Recursive filling? (15-cell expansion area to start, doubles each iteration)",
            name = "recursive",
            datatype = "GPBoolean",
            parameterType = "Required",
            direction = "Input")
      recursive.value = True
      
      rad = arcpy.Parameter(
            displayName = "Initial recursive fill radius (in cells)",
            name = "rad",
            datatype = "GPLong",
            parameterType = "Optional",
            direction = "Input")
      rad.value = 15
      
      params = [lyr, wd, template, clip, out_file, typ, recursive, rad]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      try:
         if arcpy.CheckExtension("Spatial") != "Available":
            raise Exception
      except Exception:
         return False  # tool cannot be executed

      return True  # tool can be executed

   def updateParameters(self, params):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""
      
      # import libs
      import arcpy
      import numpy as np
      import numpy.ma as ma
      from arcpy import env
      from arcpy.sa import *
      # check out Spatial Analyst for EucDistance
      arcpy.CheckOutExtension("Spatial")

      # set paths
      # output file
      out_file = params[4].valueAsText
      # scratch working dir
      wd = params[1].valueAsText
      # initial raster file, with nodata gaps to fill
      lyr = params[0].valueAsText
      # a template raster file, to mask, set extent, and get pixel size
      template = params[2].valueAsText
      # clipping region shapefile (for initial data processing subset)
      clip = params[3].valueAsText
      # end set paths

      # options
      # focal stats fill type? ('MEAN','MAJORITY','MEDIAN')
      typ = params[5].valueAsText
      # run recursively (1km fill at a time) or with one focal stats (with minimum necessary radius to fill all nodata)
      recursive = params[6].value
      rad = params[7].value

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
      # radius of focal window (beginning - doubles each time)

      r1 = arcpy.Resample_management(lyr, "r1", str(cellsize), "BILINEAR")
      r2 = arcpy.Clip_management(r1, "#", "r2", clip, "#", "ClippingGeometry")
      r2_orig = r2

      if not recursive:
         arcpy.AddMessage("Calculating focal statistics radius...")
         # retrieve maximum distance of nodata value to real values
         # for conditionally filling nodata values with mean of circular neighborhood (with radius mx)
         ed1 = EucDistance(r2)
         ed2 = ExtractByMask(ed1, template)
         maxd = arcpy.GetRasterProperties_management(ed2, "MAXIMUM")
         mx = float(maxd.getOutput(0)) * 2
         # radius equals double the maximum distance from furthest pixel from real data
         arcpy.AddMessage("Radius size: " + str(mx) + " m")

         # this would fill in nodata cells the mean in a focal neighborhood with a radius equal to the max distance from 
         # a nodata cell to a real value. It's very slow with large radius values (e.g, 5 km+)
         arcpy.AddMessage("Filling NoData areas...")
         r3 = Con(IsNull(r2),FocalStatistics(r2, NbrCircle(mx, 'MAP'),typ), r2)
         r3 = ExtractByMask(r3, template)
         r3.save(out_file)

      else:
         rad = cellsize * rad # start with specified width (rad)
         # this loop recursively fills nodata cells, increasing the fill expansion and focal window each iteration
         while ndfinal != ndtempl:
            # determine areas to fill (by 'rad' variable)
            ed1 = EucDistance(r2, rad)
            ed1 = RoundUp(ed1)
            fill_area = Con(ed1, "1", "0", "Value > 0")
            
            arcpy.AddMessage('fill NoData Expansion: ' + str(rad) + ' m')
            rad = rad * 2 # double the radius each iteration; this also makes the focal stats circular window 2x the fill area
            arcpy.AddMessage('focal stats radius size: ' + str(rad) + ' m')
            r2 = Con(fill_area,FocalStatistics(r2_orig, NbrCircle(rad, 'MAP'),typ), r2, "Value = 1")
            r2 = ExtractByMask(r2, template)
            npArray = arcpy.RasterToNumPyArray(r2,"","","",-9999)
            ndfinal = len(ma.masked_where(npArray <> -9999, npArray).compressed())
            #print ndfinal
            #print ndtempl
            arcpy.AddMessage(str(ndfinal - ndtempl) + ' more cells to fill...')

            ## DON'T FORGET TO SAVE!!
         r2.save(out_file)
         
      # clean up
      arcpy.Delete_management("r1")
      arcpy.Delete_management("r2")


# reclassify NLCD
class reclassNLCD(object):
   def __init__(self):
      self.label = "Summarize NLCD to continuous rasters"
      self.description = "Takes NLCD (including optional impervious surface and canopy coverage) data, a study region, and a raster mask, and outputs summary variables for land cover types, using neighborhood analysis, in a 3x3 window, 10-cell circle, and 100-cell circle around the focal cell"
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      out_folder = arcpy.Parameter(
            displayName="Output folder",
            name="out_folder",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
      
      project_nm = arcpy.Parameter(
            displayName="Project name (new geodatabase name/prefix for file outputs)",
            name="project_nm",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
      
      extent_shp = arcpy.Parameter(
            displayName="Output extent",
            name="extent_shp",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
      
      nlcd_classified = arcpy.Parameter(
            displayName = "NLCD classified (land cover) raster",
            name="nlcd_classified",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")
      
      impervious_raster = arcpy.Parameter(
            displayName = "NLCD impervious surface raster",
            name="impervious_raster",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")
      
      canopy_raster = arcpy.Parameter(
            displayName = "NLCD canopy coverage raster",
            name="canopy_raster",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")
      
      mask = arcpy.Parameter(
            displayName = "Raster mask for outputs",
            name="mask",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")
      
      nlcd92 = arcpy.Parameter(
            displayName = "NLCD 1992?",
            name="nlcd92",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
      nlcd92.value = True
      
      params = [out_folder,project_nm,extent_shp,nlcd_classified,impervious_raster,canopy_raster,mask,nlcd92]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      try:
         if arcpy.CheckExtension("Spatial") != "Available":
            raise Exception
      except Exception:
         return False  # tool cannot be executed

      return True  # tool can be executed

   def updateParameters(self, params):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      if not params[2].value and arcpy.CheckExtension("3d") != "Available":
            params[2].parameterType = "Required"
            
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""

      import arcpy
      import os
      from arcpy.sa import *
      from arcpy import env

      # begin variables

      # output gdb
      out_folder = params[0].valueAsText

      # file name prefix for outputs
      project_nm = params[1].valueAsText

      # study extent 
      extent_shp = params[2].valueAsText

      # input raster(s)
      nlcd_classified= params[3].valueAsText
      impervious_raster= params[4].valueAsText
      canopy_raster= params[5].valueAsText

      # optional mask
      mask = params[6].valueAsText

      # for 92 reclass
      nlcd92 = params[7].value

      # end variables
      # create new GDB
      arcpy.CreateFileGDB_management(out_folder, project_nm + ".gdb")

      # set environmental variables
      arcpy.CheckOutExtension("Spatial")
      arcpy.env.workspace = out_folder + os.sep + project_nm + ".gdb"
      arcpy.env.overwriteOutput=True

      if extent_shp:
         extent_shp = arcpy.Buffer_analysis(extent_shp, "nlcdprocextent1", buffer_distance_or_field="5000 Meters", dissolve_option="ALL")
      else:
         e1 = SetNull(nlcd_classified,nlcd_classified,"Value = 0")
         extent_shp = arcpy.RasterDomain_3d(e1, "nlcdprocextent1", "POLYGON")
         
      if mask: 
         maskshp = arcpy.RasterDomain_3d(mask, "nlcdprocextentmsk", "POLYGON")
         maskshp = arcpy.Buffer_analysis(maskshp, "nlcdprocextent2", buffer_distance_or_field="5000 Meters", dissolve_option="ALL")
         arcpy.Delete_management("nlcdprocextentmsk")
      else:
         mask = SetNull(nlcd_classified,nlcd_classified,"Value = 0")
         maskshp = arcpy.RasterDomain_3d(mask, "nlcdprocextent2", "POLYGON")
         maskshp = arcpy.Buffer_analysis(maskshp, "nlcdprocextent2", buffer_distance_or_field="5000 Meters", dissolve_option="ALL")

      extent_shp = arcpy.Intersect_analysis(["nlcdprocextent1", "nlcdprocextent2"], "nlcdprocextent")
      arcpy.Delete_management("nlcdprocextent1")
      arcpy.Delete_management("nlcdprocextent2")
      
      mask = arcpy.Clip_management(mask,"#","maskfinal", extent_shp, "#", "ClippingGeometry")

      arcpy.env.snapRaster = "maskfinal"

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
      if impervious_raster:
         output_raster="nlcd_impervious_clean"
         outsetNull=ExtractByMask(impervious_raster,in_nlcd_class)
         outsetNull=SetNull(outsetNull,outsetNull,"Value = 127")
         outsetNull.save(output_raster)
         in_impervious="nlcd_impervious_clean"

      # canopy
      if canopy_raster:
         output_raster="nlcd_canopy_clean"
         outsetNull=ExtractByMask(canopy_raster,in_nlcd_class)
         outsetNull.save(output_raster)
         in_canopy="nlcd_canopy_clean"

      ##Step 0: Set up the Remap Values

      if nlcd92:
         ## 1992 values

         #Raster values and their associated habitat in the NLCD
         #11 = Open Water
         #12 = Perennial Ice/Snow
         #21 = Low Intensity Residential
         #22 = High Intensity Residential
         #23 = Commercial/Industrial/Transportation
         #31 = Bare Rock/Sand/Clay
         #32 = Quarries/Strip Mines/Gravel Pits
         #33 = Transitional Barren
         #41 = Deciduous Forest
         #42 = Evergreen Forest
         #43 = Mixed Forest
         #51 = Shrubland
         #61 = Orchards/Vineyards/Other
         #71 = Grassland/Herbaceous
         #81 = Pasture/Hay
         #82 = Row Crops
         #83 = Small Grains
         #84 = Fallow
         #85 = Urban/Recreational Grasses
         #91 = Woody Wetlands
         #92 = Emergent Herbaceous Wetlands
         
         # 2001 CLASSES NOT IN 1992 (allows use of raster with a combination of both classification schemes)
         #24=Developed High Intensity
         #52=Shrub/Scrub
         #90= Woody Wetlands
         #95= Emergent Herbaceous Wetlands
         # ADDED TO 1992 RECLASSIFY ARRAYS: [24,0],[52,0],[90,0],[95,0]

         #For Forest we only want values 41,42,43 (GOOD for 2001)
         remap_forest=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[31,0],[32,0],[33,0],[41,1],[42,1],[43,1],[51,0],[61,0],[71,0],[81,0],[82,0],[83,0],[84,0],[85,0],[91,0],[92,0],
            [24,0],[52,0],[90,0],[95,0]])

         #For Wetland we only want 91 and 92 (ADDED 90 95 for 2001)
         remap_wetland=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[31,0],[32,0],[33,0],[41,0],[42,0],[43,0],[51,0],[61,0],[71,0],[81,0],[82,0],[83,0],[84,0],[85,0],[91,1],[92,1],
            [24,0],[52,0],[90,1],[95,1]])

         #For Open Area we want 31,32,33,61,71,81,82,83,84 (not 85) - all barren, agricultural (including orchard [61]) (GOOD for 2001)
         remap_Open=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[31,1],[32,1],[33,1],[41,0],[42,0],[43,0],[51,0],[61,1],[71,1],[81,1],[82,1],[83,1],[84,1],[85,0],[91,0],[92,0],
            [24,0],[52,0],[90,0],[95,0]])

         #For Water we want 11 (GOOD FOR 2001)
         remap_water=RemapValue([[11,1],[12,0],[21,0],[22,0],[23,0],[31,0],[32,0],[33,0],[41,0],[42,0],[43,0],[51,0],[61,0],[71,0],[81,0],[82,0],[83,0],[84,0],[85,0],[91,0],[92,0],
            [24,0],[52,0],[90,0],[95,0]])

         #For ShrubScrub we want 51 (ADDED 52 for 2001)
         remap_ShrubScrub=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[31,0],[32,0],[33,0],[41,0],[42,0],[43,0],[51,1],[61,0],[71,0],[81,0],[82,0],[83,0],[84,0],[85,0],[91,0],[92,0],
            [24,0],[52,1],[90,0],[95,0]])

         #For ConiferForest we want 42 (GOOD FOR 2001)
         remap_evergreen=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[31,0],[32,0],[33,0],[41,0],[42,1],[43,0],[51,0],[61,0],[71,0],[81,0],[82,0],[83,0],[84,0],[85,0],[91,0],[92,0],
            [24,0],[52,0],[90,0],[95,0]])

         #For Deciduous/Mix we want 41 and 43 and we want 43 half as much so 41->100 and 43->50 (GOOD FOR 2001)
         remap_decidmix=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[31,0],[32,0],[33,0],[41,100],[42,0],[43,50],[51,0],[61,0],[71,0],[81,0],[82,0],[83,0],[84,0],[85,0],[91,0],[92,0],
            [24,0],[52,0],[90,0],[95,0]])

         #For Evergreen/Mix we want 42 and 43 and we want 43 half as much so 42->100 and 43->50 (GOOD FOR 2001)
         remap_evermix=RemapValue([[11,0],[12,0],[21,0],[22,0],[23,0],[31,0],[32,0],[33,0],[41,0],[42,100],[43,50],[51,0],[61,0],[71,0],[81,0],[82,0],[83,0],[84,0],[85,0],[91,0],[92,0],
            [24,0],[52,0],[90,0],[95,0]])

      else:

         ## 2001, 2006, 2011 values

         #Raster values and their associated habitat in the NLCD
         #11 = Open Water
         #12 = Perennial Ice/Snow
         #21 = Developed Open Space
         #22 = Developed Low Intensity
         #23 = Developed Medium Intensity
         #24 = Developed High Intensity
         #31 = Barren Land
         #41 = Deciduous Forest
         #42 = Evergreen Forest
         #43 = Mixed Forest
         #52 = Shrub/Scrub
         #71 = Grassland/Herbaceous
         #81 = Pasture/Hay
         #82 = Cultivated Crops
         #90 = Woody Wetlands
         #95 = Emergent Herbaceous Wetlands

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
      
      #out_reclassify_forest=Reclassify(inraster,reclass_field,remap_forest,"NODATA")
      #out_reclassify_forest.save(project_nm + "_b_forest_n")

      out_reclassify_wetland=Reclassify(inraster,reclass_field,remap_wetland,"NODATA")
      out_reclassify_wetland.save(project_nm + "_b_wetland_n")

      out_reclassify_open=Reclassify(inraster,reclass_field,remap_Open,"NODATA")
      out_reclassify_open.save(project_nm + "_b_open_n")

      out_reclassify_water=Reclassify(inraster,reclass_field,remap_water,"NODATA")
      out_reclassify_water.save(project_nm + "_b_water_n")

      out_reclassify_ShrubScrub=Reclassify(inraster,reclass_field,remap_ShrubScrub,"NODATA")
      out_reclassify_ShrubScrub.save(project_nm + "_b_shrubscrub_n")

      #########Added 2017 - Split the forest into evergreen/mixed forest and deciduous/mixed forest

      #out_reclassify_Evergreen=Reclassify(inraster,reclass_field,remap_evergreen,"NODATA")
      #out_reclassify_Evergreen.save(project_nm + "_b_evergreen_n")

      out_reclassify_decidmix=Reclassify(inraster,reclass_field,remap_decidmix,"NODATA")
      out_reclassify_decidmix.save(project_nm + "_b_decidmix_n")

      out_reclassify_Evermix=Reclassify(inraster,reclass_field,remap_evermix,"NODATA")
      out_reclassify_Evermix.save(project_nm + "_b_evermix_n")

      arcpy.AddMessage("Done reclassifying")
      #Step 3: Calculate focal statistics

      # get list of binary rasters and add impervious and canopy to it
      proj_source=arcpy.ListRasters(project_nm  + "_b_*")
      if impervious_raster:
         proj_source.append(in_impervious)
      if canopy_raster:
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
          
          arcpy.AddMessage("Calculating focal statistics for "+basename + "...")

          out_raster_1=project_nm + "_" + basename+"_1"
          out_raster_10=project_nm + "_" + basename+"_10"
          out_raster_100=project_nm + "_" + basename+"_100"
          print "Calculating neighborhood 1 cell square"
          outFocal_1=FocalStatistics(raster,neighborhood_1,"MEAN","DATA")
          outFocal_1=Con(IsNull(outFocal_1),0, outFocal_1)
          outFocal_1=ExtractByMask(outFocal_1,mask)
          outFocal_1.save(out_raster_1)
          print "Finished with first neighborhood"
          print "Calculating neighborhood 10 cell circle"
          outFocal_10=FocalStatistics(raster,neighborhood_10,"MEAN","DATA")
          outFocal_10=Con(IsNull(outFocal_10),0, outFocal_10)
          outFocal_10=ExtractByMask(outFocal_10,mask)
          outFocal_10.save(out_raster_10)
          print "Finished with second neighborhood"
          print "Calculating neighborhood 100 cell circle"
          outFocal_100=FocalStatistics(raster,neighborhood_100,"MEAN","DATA")
          outFocal_100=Con(IsNull(outFocal_100),0, outFocal_100)
          outFocal_100=ExtractByMask(outFocal_100,mask)
          outFocal_100.save(out_raster_100)
          arcpy.AddMessage("Finished with "+basename + ".")
          
      ## clean up
      if arcpy.Exists("maskfinal"):
          arcpy.Delete_management("maskfinal")
      arcpy.Delete_management("nlcdprocextent")
      arcpy.Delete_management("nlcd_cliptemp")

      return
      
# reclassify CCAP
class reclassCCAP(object):
   def __init__(self):
      self.label = "Summarize CCAP to continuous rasters"
      self.description = "Takes CCAP (including optional NLCD impervious surface and canopy coverage) data, a study region, and a raster mask, and outputs summary variables for land cover types, using neighborhood analysis, in a 3x3 window, 10-cell circle, and 100-cell circle around the focal cell"
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      out_folder = arcpy.Parameter(
            displayName="Output folder",
            name="out_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
      
      project_nm = arcpy.Parameter(
            displayName="Project name (new geodatabase name/prefix for file outputs)",
            name="project_nm",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
      
      extent_shp = arcpy.Parameter(
            displayName="Output extent",
            name="extent_shp",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
      
      ccap_classified = arcpy.Parameter(
            displayName = "CCAP classified (land cover) raster",
            name="ccap_classified",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")
      
      impervious_raster = arcpy.Parameter(
            displayName = "NLCD impervious surface raster",
            name="impervious_raster",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")
      
      canopy_raster = arcpy.Parameter(
            displayName = "NLCD canopy coverage raster",
            name="canopy_raster",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")
      
      mask = arcpy.Parameter(
            displayName = "Raster mask for outputs",
            name="mask",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")
      
      params = [out_folder,project_nm,extent_shp,ccap_classified,impervious_raster,canopy_raster,mask]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      try:
         if arcpy.CheckExtension("Spatial") != "Available":
            raise Exception
      except Exception:
         return False  # tool cannot be executed

      return True  # tool can be executed

   def updateParameters(self, params):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      if not params[2].value and arcpy.CheckExtension("3d") != "Available":
            params[2].parameterType = "Required"
            
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""

      import arcpy
      import os
      from arcpy.sa import *
      from arcpy import env

      # begin variables

      # output gdb
      out_folder = params[0].valueAsText

      # file name prefix for outputs
      project_nm = params[1].valueAsText

      # study extent 
      extent_shp = params[2].valueAsText

      # input raster(s)
      ccap_classified= params[3].valueAsText
      impervious_raster= params[4].valueAsText
      canopy_raster= params[5].valueAsText

      # optional mask
      mask = params[6].valueAsText

      # end variables
            
      # create new GDB
      arcpy.CreateFileGDB_management(out_folder, project_nm + ".gdb")

      # set environmental variables
      arcpy.CheckOutExtension("Spatial")
      arcpy.env.workspace = out_folder + os.sep + project_nm + ".gdb"
      arcpy.env.overwriteOutput=True
      
      if extent_shp:
         extent_shp = arcpy.Buffer_analysis(extent_shp, "ccapprocextent1", buffer_distance_or_field="5000 Meters", dissolve_option="ALL")
      else:
         e1 = SetNull(ccap_classified,ccap_classified,"Value = 0")
         extent_shp = arcpy.RasterDomain_3d(e1, "ccapprocextent1", "POLYGON")
         
      if mask: 
         maskshp = arcpy.RasterDomain_3d(mask, "ccapprocextentmsk", "POLYGON")
         maskshp = arcpy.Buffer_analysis(maskshp, "ccapprocextent2", buffer_distance_or_field="5000 Meters", dissolve_option="ALL")
         arcpy.Delete_management("ccapprocextentmsk")
      else:
         mask = SetNull(ccap_classified,ccap_classified,"Value = 0")
         maskshp = arcpy.RasterDomain_3d(mask, "ccapprocextent2", "POLYGON")
         maskshp = arcpy.Buffer_analysis(maskshp, "ccapprocextent2", buffer_distance_or_field="5000 Meters", dissolve_option="ALL")

      extent_shp = arcpy.Intersect_analysis(["ccapprocextent1", "ccapprocextent2"], "ccapprocextent")
      arcpy.Delete_management("ccapprocextent1")
      arcpy.Delete_management("ccapprocextent2")
      
      mask = arcpy.Clip_management(mask,"#","maskfinal", extent_shp, "#", "ClippingGeometry")

      arcpy.env.snapRaster = "maskfinal"

      # clean (clip and set null) rasters
      # nlcd classified
      arcpy.AddMessage("Clipping CCAP...")
      in_nlcd = arcpy.Clip_management(ccap_classified,"#","ccap_cliptemp", extent_shp, "#", "ClippingGeometry")
      inraster= "ccap_cliptemp"
      where_clause="Value = 0 OR Value = 1"  # Value = 1 is unclassified
      output_raster="ccap_classified_clean"
      outsetNull=SetNull(inraster,inraster,where_clause)
      outsetNull.save(output_raster)
      in_nlcd_class="ccap_classified_clean"

      # impervious
      if impervious_raster:
         arcpy.AddMessage("Clipping impervious raster...")
         output_raster="nlcd_impervious_clean"
         outsetNull=ExtractByMask(impervious_raster,in_nlcd_class)
         outsetNull=SetNull(outsetNull,outsetNull,"Value = 127")
         outsetNull.save(output_raster)
         in_impervious="nlcd_impervious_clean"

      # canopy
      if canopy_raster:
         arcpy.AddMessage("Clipping canopy raster...")
         output_raster="nlcd_canopy_clean"
         outsetNull=ExtractByMask(canopy_raster,in_nlcd_class)
         outsetNull.save(output_raster)
         in_canopy="nlcd_canopy_clean"


      ##Step 0: Set up the Remap Values
      #Raster values and their associated habitat in CCAP
      #0 = background
      #1 = unclassified
      #2 = Developed High Intensity
      #3 = Developed Medium Intensity
      #4 = Developed Low Intensity
      #5 = Developed Open Space
      #6 = Cultivated Crops
      #7 = Pasture/Hay
      #8 = Grassland/Herbaceous
      #9 = Deciduous Forest
      #10 = Evergreen Forest
      #11 = Mixed Forest
      #12 = Shrub/Scrub
      #13 = Palustrine Forested Wetland **DIFFERENT FROM NLCD**
      #14 = Palustrine Scrub/Shrub wetland **DIFFERENT FROM NLCD**
      #15 = Palustrine Emergent Wetland (persistent) **DIFFERENT FROM NLCD**
      #16 = Estuarine Forested Wetland **DIFFERENT FROM NLCD**
      #17 = Esturaine Scrub/Shrub Wetland **DIFFERENT FROM NLCD**
      #18 = Estuarine Emergent Wetland **DIFFERENT FROM NLCD**
      #19 = Unconsolidated shore **DIFFERENT FROM NLCD**
      
      # Barren lands
      #20 = Barren Land
      #24 = Tundra
      #25 = Perennial Ice/Snow
      
      # Water/submerged lands
      #21 = Open Water
      #22 Palustrine Aquatic Bed **DIFFERENT FROM NLCD**
      #23 Estuarine Aquatic Bed **DIFFERENT FROM NLCD**
      
      # template_allzeros([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,0],[20,0],[21,0],[22,0],[23,0],[24,0],[25,0]])

      #For Forest we only want values 9,10,11
      remap_forest=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,1],[10,1],[11,1],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,0],[20,0],[21,0],[22,0],[23,0],[24,0],[25,0]])

      #For Open Area we want 8,7,6
      remap_Open=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,1],[7,1],[8,1],[9,0],[10,0],[11,0],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,0],[20,1],[21,0],[22,0],[23,0],[24,0],[25,0]])

      #For Water we want 21
      remap_water=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,0],[20,0],[21,1],[22,0],[23,0],[24,0],[25,0]])

      #For ShrubScrub we want 12
      remap_ShrubScrub=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,1],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,0],[20,0],[21,0],[22,0],[23,0],[24,0],[25,0]])

      #For Deciduous/Mix we want 9 and 11 and we want 11 half as much so 9->100 and 11->50
      remap_decidmix=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,100],[10,0],[11,50],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,0],[20,0],[21,0],[22,0],[23,0],[24,0],[25,0]])

      #For Evergreen/Mix we want 10 and 11 and we want 11 half as much so 10->100 and 11->50
      remap_evermix=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,100],[11,50],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,0],[20,0],[21,0],[22,0],[23,0],[24,0],[25,0]])

      ## CCAP-specific types
      # unconsolidated shore/ bare ground (19, 20)
      remap_shore=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,0],[19,1],[20,1],[21,0],[22,0],[23,0],[24,0],[25,0]])
      
      # estuarine woody (16,17)
      remap_estwoody=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,0],[13,0],[14,0],[15,0],[16,1],[17,1],[18,0],[19,0],[20,0],[21,0],[22,0],[23,0],[24,0],[25,0]])
      # palustrine woody (13,14)
      remap_palwoody=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,0],[13,1],[14,1],[15,0],[16,0],[17,0],[18,0],[19,0],[20,0],[21,0],[22,0],[23,0],[24,0],[25,0]])
      
      # estuarine herb. veg (18,23))
      remap_estherb=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,0],[13,0],[14,0],[15,0],[16,0],[17,0],[18,1],[19,0],[20,0],[21,0],[22,0],[23,1],[24,0],[25,0]])
      # palustrine herb. veg (15, 22)
      remap_palherb=RemapValue([[0,0],[1,0],[2,0],[3,0],[4,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0],[11,0],[12,0],[13,0],[14,0],[15,1],[16,0],[17,0],[18,0],[19,0],[20,0],[21,0],[22,1],[23,0],[24,0],[25,0]])

      # do reclassifys
      inraster= in_nlcd_class
      
      arcpy.AddMessage("Reclassifying...")
      #Step 2 - Reclass the rasters for each desired land type
      reclass_field= "Value"
      
      # excluded
      #out_reclassify_forest=Reclassify(inraster,reclass_field,remap_forest,"NODATA")
      #out_reclassify_forest.save(project_nm + "_b_forest_n")

      out_reclassify_open=Reclassify(inraster,reclass_field,remap_Open,"NODATA")
      out_reclassify_open.save(project_nm + "_b_open_n")

      out_reclassify_water=Reclassify(inraster,reclass_field,remap_water,"NODATA")
      out_reclassify_water.save(project_nm + "_b_water_n")

      out_reclassify_ShrubScrub=Reclassify(inraster,reclass_field,remap_ShrubScrub,"NODATA")
      out_reclassify_ShrubScrub.save(project_nm + "_b_shrubscrub_n")

      out_reclassify_decidmix=Reclassify(inraster,reclass_field,remap_decidmix,"NODATA")
      out_reclassify_decidmix.save(project_nm + "_b_decidmix_n")

      out_reclassify_Evermix=Reclassify(inraster,reclass_field,remap_evermix,"NODATA")
      out_reclassify_Evermix.save(project_nm + "_b_evermix_n")
      
      ## CCAP-specific types
      out_reclassify_shore=Reclassify(inraster,reclass_field,remap_shore,"NODATA")
      out_reclassify_shore.save(project_nm + "_b_bareshore_n")
      
      out_reclassify_estwoody=Reclassify(inraster,reclass_field,remap_estwoody,"NODATA")
      out_reclassify_estwoody.save(project_nm + "_b_estwoody_n")
      
      out_reclassify_palwoody=Reclassify(inraster,reclass_field,remap_palwoody,"NODATA")
      out_reclassify_palwoody.save(project_nm + "_b_palwoody_n")
      
      out_reclassify_estherb=Reclassify(inraster,reclass_field,remap_estherb,"NODATA")
      out_reclassify_estherb.save(project_nm + "_b_estherb_n")
      
      out_reclassify_palherb=Reclassify(inraster,reclass_field,remap_palherb,"NODATA")
      out_reclassify_palherb.save(project_nm + "_b_palherb_n")
      
      arcpy.AddMessage("Done reclassifying")
      #Step 3: Calculate focal statistics

      # get list of binary rasters and add impervious and canopy to it
      proj_source=arcpy.ListRasters(project_nm  + "_b_*")
      if impervious_raster:
         proj_source.append(in_impervious)
      if canopy_raster:
         proj_source.append(in_canopy)

      neighborhood_1=NbrRectangle(3,3,"CELL")
      neighborhood_10=NbrCircle(10,"CELL")
      neighborhood_100=NbrCircle(100,"CELL")

      for raster in proj_source:
          if "forest" in raster:
              basename="mean_forest"
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
          elif "decidmix" in raster:
              basename="mean_deciduous_mixed_n"
          elif "evermix" in raster:
              basename="mean_evergreen_mixed_n"
          elif "bareshore" in raster:
              basename="mean_bareshore_n"
          elif "estwoody" in raster:
              basename="mean_estwoody_n"
          elif "palwoody" in raster:
              basename="mean_palwoody_n"
          elif "estherb" in raster:
              basename="mean_estherb_n"
          elif "palherb" in raster:
              basename="mean_palherb_n"
          else:
              continue
          
          arcpy.AddMessage("Calculating focal statistics for "+basename + "...")

          out_raster_1=project_nm + "_" + basename+"_1"
          out_raster_10=project_nm + "_" + basename+"_10"
          out_raster_100=project_nm + "_" + basename+"_100"
          print "Calculating neighborhood 1 cell square"
          outFocal_1=FocalStatistics(raster,neighborhood_1,"MEAN","DATA")
          outFocal_1=Con(IsNull(outFocal_1),0, outFocal_1)
          outFocal_1=ExtractByMask(outFocal_1,mask)
          outFocal_1.save(out_raster_1)
          print "Finished with first neighborhood"
          print "Calculating neighborhood 10 cell circle"
          outFocal_10=FocalStatistics(raster,neighborhood_10,"MEAN","DATA")
          outFocal_10=Con(IsNull(outFocal_10),0, outFocal_10)
          outFocal_10=ExtractByMask(outFocal_10,mask)
          outFocal_10.save(out_raster_10)
          print "Finished with second neighborhood"
          print "Calculating neighborhood 100 cell circle"
          outFocal_100=FocalStatistics(raster,neighborhood_100,"MEAN","DATA")
          outFocal_100=Con(IsNull(outFocal_100),0, outFocal_100)
          outFocal_100=ExtractByMask(outFocal_100,mask)
          outFocal_100.save(out_raster_100)
          arcpy.AddMessage("Finished with "+basename + ".")
          
      ## clean up
      if arcpy.Exists("maskfinal"):
          arcpy.Delete_management("maskfinal")
      arcpy.Delete_management("ccapprocextent")
      arcpy.Delete_management("ccap_cliptemp")

      return