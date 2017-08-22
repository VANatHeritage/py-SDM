import arcpy


class Toolbox(object):
   def __init__(self):
      self.label = "Environmental variables processing"
      self.alias = "envvarproc"

      # List of tool classes associated with this toolbox (defined classes below)
      self.tools = [finalizeEnvVar, rasterFill]

# finalize environmental variables
class finalizeEnvVar(object):
   def __init__(self):
      self.label = "Finalize Environmental Variables"
      self.description ="Takes input raster, an optional a raster mask, " + \
                        "and a multiplier. Values are multiplied by the " + \
                        "multiplier and the raster is converted to integer. " + \
                        "The raster is also masked if a mask is provided."
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

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
      """The source code of the tool."""

      from arcpy.sa import *

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
            datatype="DEFolder",
            parameterType="Required",
            direction="Output")
      
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
      recursive.defaultEnvironmentName = True
      
      params = [out_file, wd, lyr, template, clip, typ, recursive]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      try:
         if arcpy.CheckExtension("Spatial") != "Available":
            raise Exception
      except Exception:
         return False  # tool cannot be executed

      return True  # tool can be executed

   def updateParameters(self, parameters):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      return

   def updateMessages(self, parameters):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, parameters, messages):
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
      out_file = params[0].valueAsText
      # scratch working dir
      wd = params[1].valueAsText
      # initial raster file, with nodata gaps to fill
      lyr = params[2].valueAsText
      # a template raster file, to mask, set extent, and get pixel size
      template = params[3].valueAsText
      # clipping region shapefile (for initial data processing subset)
      clip = params[4].valueAsText
      # end set paths

      # options
      # focal stats fill type? ('MEAN','MAJORITY','MEDIAN')
      typ = params[5].valueAsText
      # run recursively (1km fill at a time) or with one focal stats (with minimum necessary radius to fill all nodata)
      recursive = params[6].valueAsText

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

      r1 = arcpy.Resample_management(lyr, wd + "r1.tif", str(cellsize), "BILINEAR")
      r2 = arcpy.Clip_management(r1, "#", wd + "r2.tif", clip, "#", "ClippingGeometry")
      r2_orig = r2

      # con to mask out values for water areas

      if not recursive:

         # retrieve maximum distance of nodata value to real values
         # for conditionally filling nodata values with mean of circular neighborhood (with radius mx)
         ed1 = EucDistance(r2)
         ed2 = ExtractByMask(ed1, template)
         maxd = arcpy.GetRasterProperties_management(ed2, "MAXIMUM")
         mx = float(maxd.getOutput(0)) + 90
         # the +90 ensures that all pixels should get more than one pixel of real data in their focal window
         print 'Radius size: ' + str(mx) + ' m'

         # this would fill in nodata cells the mean in a focal neighborhood with a radius equal to the max distance from 
         # a nodata cell to a real value. It's very slow with large radius values (e.g, 5 km+)
         r3 = Con(IsNull(r2),FocalStatistics(r2, NbrCircle(mx, 'MAP'),typ), r2)
         r3 = ExtractByMask(r3, template)
         r3.save(out_file)

      else:
         rad = cellsize * 15 # start with 15-cell width fill (15*30 = 450m)
         # this loop recursively fills nodata cells, increasing the fill expansion and focal window each iteration
         while ndfinal != ndtempl:
            # determine areas to fill (by 'rad' variable)
            ed1 = EucDistance(r2, rad)
            ed1 = RoundUp(ed1)
            fill_area = Con(ed1, "1", "0", "Value > 0")
            
            print 'fill NoData Expansion: ' + str(rad) + ' m'
            rad = rad * 2 # double the radius each iteration; this also makes the focal stats circular window 2x the fill area
            print 'focal stats radius size: ' + str(rad) + ' m'
            r2 = Con(fill_area,FocalStatistics(r2_orig, NbrCircle(rad, 'MAP'),typ), r2, "Value = 1")
            r2 = ExtractByMask(r2, template)
            npArray = arcpy.RasterToNumPyArray(r2,"","","",-9999)
            ndfinal = len(ma.masked_where(npArray <> -9999, npArray).compressed())
            print ndfinal
            print ndtempl

            ## DON'T FORGET TO SAVE!!
            r2.save(out_file)
