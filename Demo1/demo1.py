# **********************************************************************
#
# NAME: Your Name
# DATE: date
# CLASS: GEOG410
# ASSIGNMENT: Lab #
#
# DESCRIPTION: describe the script, what it does, how it does it,
#       and any other important information
#
# INSTRUCTIONS: usage instructions, i.e., inputs, outputs, and how to
#       run the script
#
# SOURCE(S): list any sources used to complete this script
#
# **********************************************************************

# ********** IMPORT STATEMENTS **********
import sys
import os
import glob
import arcpy
from arcpy import env


# ********** GLOBAL CONSTANTS **********
# CONSTANTS ARE ALL UPPERCASE PER PYTHON CONVENTIONS
PY_FILE_DIR = os.path.dirname(os.path.abspath(__file__))  # get the path to the .py file
DATA_DIR = os.path.join(PY_FILE_DIR, "data")

# GDB settings
GDB_NAME = "treeDamage"
FDS_DATA_NAME = "Data"
FDS_RESULTS_NAME = "Results"
GDB_EXT = ".gdb"

# scratch settings -- use a constant, so we can change setting if we want to keep file
INTERMEDIATE_WORKSPACE = "in_memory"

# data CRS
CRS = arcpy.SpatialReference(2913)  # NAD_1983_HARN_StatePlane_Oregon_North_FIPS_3601_Feet_Intl

# required FCs for analysis
TREES = "trees"
BUILDINGS = "buildings"
ZONING = "zoning"
REQUIRED_FCS = [TREES,
                BUILDINGS,
                ZONING,
                ]

# analysis settings and fields
ANALYSIS_HEIGHT = 30  # in feet
TREE_BUFF_FIELD = "Height"

ZONING_CLASS_FIELD = "ZONEGEN_CL"
ZONING_CLASSES = ["RUR", "MUR", "MFR", "SFR"]

# output FC
AT_RISK_BUILDINGS = "AtRiskBuildings"


# ********** FUNCTIONS **********

def create_gdb(location, name, overwrite=False):
    """
    """
    # capture current overwrite setting
    overwritesetting = env.overwriteOutput
    # set env overwrite to match argument
    env.overwriteOutput = overwrite

    if not name.endswith(GDB_EXT):
        name += GDB_EXT

    geodatabase = os.path.join(location, name)

    # try to create the gdb
    try:
        arcpy.CreateFileGDB_management(location, name)
    finally:
        # set overwrite back to previous setting
        env.overwriteOutput = overwritesetting

    return geodatabase


def create_fds(gdbpath, fdsname, spatialref):
    """Creates a feature dataset with the name supplied by fdsname
    in the geodatabase given by gdbpath. The feature dataset will
    have the spatial reference defeined by spatialref, which is an
    arcpy SpatialReference object passed into the function.

    If a fds already exists with the same name, this function will
    simply do nothing.

    This function returns the full path to the fds inside the
    geodatabase.
    """
    fds = os.path.join(gdbpath, fdsname)

    if not arcpy.Exists(fds):
        arcpy.CreateFeatureDataset_management(gdbpath, fdsname, spatialref)

    return fds


def import_shapefiles_in_directory(directory, gdb_path, fds_name=None):
    """
    """
    if fds_name:
        gdb_path = os.path.join(gdb_path, fds_name)


    for shapefile in get_shapefiles_in_directory(directory):
        shapefilename = os.path.splitext(os.path.basename(shapefile))[0]

        # need to ensure CRS matches FDS
        if arcpy.Describe(shapefile).SpatialReference == CRS:
            arcpy.CopyFeatures_management(shapefile,
                                          os.path.join(gdb_path, shapefilename)
                                          )
        else:
            arcpy.Project_management(shapefile,
                                     os.path.join(gdb_path, shapefilename),
                                     CRS
                                     )


def get_shapefiles_in_directory(directory):
    """
    """
    return glob.glob(os.path.join(directory, "*.shp"))  # query is like data\*.shp


def check_for_required_fcs(location, fcslist):
    """
    """
    errors = []

    for fc in fcslist:
        if not arcpy.Exists(os.path.join(location, fc)):
            errors.append("Missing required feature class {} in {}.".format(fc, location))

    return errors


def build_zoning_query(zoningfc):
    """
    """
    query = ""
    for zoneclass in ZONING_CLASSES:
        query += "{} = '{}' OR ".format(arcpy.AddFieldDelimiters(zoningfc, ZONING_CLASS_FIELD),
                                        zoneclass)
    return query[:-4]


# ********** MAIN **********

def main():
    # create file geodatabase
    print ">Creating geodatabase {} in {}".format(GDB_NAME, DATA_DIR)
    fgdb = create_gdb(DATA_DIR, GDB_NAME, overwrite=True)

    # create feature datasets in geodatabase
    print ">Creating feature datasets in geodatabase"
    fds_data = create_fds(fgdb, FDS_DATA_NAME, CRS)
    fds_results = create_fds(fgdb, FDS_RESULTS_NAME, CRS)

    # copy shapefiles into data fds
    print ">Copying shapefiles into {}".format(fds_data)
    import_shapefiles_in_directory(DATA_DIR, fgdb, fds_name=FDS_DATA_NAME)

    # make sure all necessary files are present
    print ">Validating copied FCs"
    missing_fcs = check_for_required_fcs(fds_data, REQUIRED_FCS)
    if missing_fcs:
        for fc in missing_fcs:
            print fc
        raise Exception("Required feature class(es) missing. Aborting.")

    # find all large trees (>= analysis height)
    print ">Finding all large trees"
    trees = os.path.join(fds_data, TREES)
    treequery = "{} >= {}".format(arcpy.AddFieldDelimiters(trees, TREE_BUFF_FIELD),
                                  ANALYSIS_HEIGHT)
    # selection is via def query
    lrgtrees_lyr = arcpy.MakeFeatureLayer_management(trees, "treeslyr", treequery)

    # uncomment to keep buffers by re-setting "constant" to results fds
    #INTERMEDIATE_WORKSPACE = fds_results

    # buffer trees by tree height
    print ">Buffering trees to find fall radius"
    treebuffers = arcpy.Buffer_analysis(lrgtrees_lyr,
                                        os.path.join(INTERMEDIATE_WORKSPACE, "treebuff"),
                                        TREE_BUFF_FIELD)

    # find resi zones
    print ">Finding residential zones"
    zoning = os.path.join(fds_data, ZONING)
    zoningquery = build_zoning_query(zoning)
    zoning_lyr = arcpy.MakeFeatureLayer_management(zoning, "zonelyr")
    # can also use select by attributes with a feature layer
    arcpy.SelectLayerByAttribute_management(zoning_lyr,
                                            where_clause=zoningquery)

    # create buildings lyr
    print ">Creating buildings feature layer"
    buildings = os.path.join(fds_data, BUILDINGS)
    buildings_lyr =  arcpy.MakeFeatureLayer_management(buildings, "buildingslyr")

    # find buildings in wanted zones
    print ">Finding buildings in wanted zones"
    arcpy.SelectLayerByLocation_management(buildings_lyr,
                                           "HAVE_THEIR_CENTER_IN",
                                           zoning_lyr)

    # find buildings inside tree fall radius
    print ">Finding buildings inside tree fall radius"
    arcpy.SelectLayerByLocation_management(buildings_lyr,
                                           "INTERSECT",
                                           treebuffers,
                                           selection_type="SUBSET_SELECTION")

    if int(arcpy.GetCount_management(buildings_lyr).getOutput(0)):
        outputfc = os.path.join(fds_results, AT_RISK_BUILDINGS)
        arcpy.CopyFeatures_management(buildings_lyr,
                                      outputfc)
        print "\nFound at-risk buildings; features written to {}".format(outputfc)
    else:
        print "\nNo buildings at risk."

    return 0


# ********** MAIN CHECK **********

if __name__ == '__main__':
    sys.exit(main())
