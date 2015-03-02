# **********************************************************************
#
# NAME: Jarrett Keifer
# DATE: 2015-03-01
#
# DESCRIPTION: Calculate slope and/or aspect from a continuous raster dataset.
#       Too calculation methods possible: RITTER and HORN. RITTER is higher
#       accuracy and faster, but HORN is the most widely-implemented method.
#       (Use HORN if needing results to be consistent with ArcGIS or other
#       major GIS software.) RITTER is the default.
#
#       When generating slope, the user can choose to output the slope in
#       degrees or percent rise (default is degrees). Also, slope expects
#       the horizontal (x, y) units to be the same as the vertical units;
#       if this is not true, an optional conversion factor can be applied
#       to scale the horizontal uints to the vertical units.
#
#       Aspect generation has an option to output in compass direction
#       (default) or absolute direction. Units do not matter for aspect.
#
#       In both cases, an overwrite option can be supplied to allow the
#       the program to overwrite an existing dataset if it has the same
#       name as one of the output files.
#
# INSTRUCTIONS: Run this script from the command line as an argument of
#       python. The script takes the follwing optional arguments:
#
#           -s path to slope raster (output)
#           -a path to aspect raster (output)
#           -m slope calculation method: options are RITTER or HORN
#           -p use percent rise rather than degrees for slope output
#           -c conversion factor (float) from horizontal to vertical units
#           -b use absolute directions rather than compass directions for
#              aspect output
#           -o overwrite any existing datasets
#           -f GDAL driver name to use (default is same as input)
#
#       The path to the input raster is a positional argument and can be
#       supplied at any position in the command.
#
# SOURCE(S): - ESRI documentation on Slope and Aspect
#            - Digital Terrain Modeling: Principles and Methodology by
#                  Li, Zhu, and Gold
#
# **********************************************************************

# ********** IMPORT STATEMENTS **********
import sys
import os
import argparse
from math import atan, sqrt, degrees, atan2
from osgeo import gdal
from osgeo.gdalconst import GA_Update, GA_ReadOnly
from scipy import ndimage


# ********** CONSTANTS **********

SLOPE_CALC_METHODS = ["RITTER", "HORN"]
DEFAULT_SLOPE_METHOD = SLOPE_CALC_METHODS[0]

# ********** FUNCTIONS **********

def parse_arguments(argv):
    """Parse command line arguments and return as a dictionary
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("elevation_raster", type=str,
                        help="path to the elevation raster")
    parser.add_argument("-s", "--slope_raster", type=str,
                        help="path at which to create the slope raster")
    parser.add_argument("-a", "--aspect_raster", type=str,
                        help="path at which to create the aspect raster.")
    parser.add_argument('-o', '--overwrite', required=False, action="store_true",
                        help='option to allow overwrite of existing files')
    parser.add_argument('-p', '--percent_slope', action="store_true",
                        help='output slope in percent instead of degrees')
    parser.add_argument('-b', '--absolute_aspect', action="store_true",
                        help='output aspect with absolute direction rather than compass direction')
    parser.add_argument('-m', '--slope_method', choices=SLOPE_CALC_METHODS,
                        default=DEFAULT_SLOPE_METHOD,
                        help='slope calculation method; default is RITTER')
    parser.add_argument('-f', '--gdal_format', type=str,
                        default=None,
                        help='GDAL driver name for output file format; default is same as input')
    parser.add_argument('-c', '--conversion_factor', type=float, default=1,
                        help='conversion factor from ground units to elevation units')
    args = parser.parse_args(argv)
    return vars(args)


def open_raster(infilepath, readonly=True):
    """Open a raster file as a GDAL dataset. Set the readonly argument to
    True to get update (write) access to the file.
    """
    # if readonly then use ReadOnly access
    if readonly is True:
        raster = gdal.Open(infilepath, GA_ReadOnly)
    # otherwise use Update access
    elif readonly is False:
        raster = gdal.Open(infilepath, GA_Update)
    else:
        # could not understand the readonly value
        raise Exception("Error: the read status could not be be determined.")

    # GDAL will return None from Open if failed to open file
    if raster is None:
        raise Exception("Error encountered opening file.")

    return raster


def create_new_raster(outpath, cols, rows, bands, datatype, drivername,
                      geotransform=None, projection=None, overwrite=False):
    """
    """
    #
    driver = gdal.GetDriverByName(drivername)

    #
    if not driver:
        raise Exception("Driver specified is not a valid GDAL Raster Driver.")

    #
    driver.Register()

    #
    if overwrite:
        if os.path.exists(outpath):
            driver.Delete(outpath)

    #
    raster = driver.Create(outpath, cols, rows, bands, datatype)

    #
    if raster is None:
        raise Exception("Error encountered creating output raster.")

    #
    if geotransform:
        raster.SetGeoTransform(geotransform)

    #
    if projection:
        raster.SetProjection(projection)

    return raster


def blank_raster_from_existing_raster(inraster,
                                      outpath,
                                      numberofbands=None,
                                      drivername=None,
                                      datatype=None,
                                      cols=None,
                                      rows=None,
                                      geotransform=None,
                                      projection=None,
                                      overwrite=False):
    """
    """
    # get driver name from inraster if not specified
    if drivername is None:
        drivername = inraster.GetDriver().GetDescription()

    # get band type from band 1 of inraster if not specified
    if datatype is None:
        band = inraster.GetRasterBand(1)
        datatype = band.DataType
        band = None

    # get number of columns from inraster if not specified
    if cols is None:
        cols = inraster.RasterXSize

    # get number of rows from inraster if not specified
    if rows is None:
        rows = inraster.RasterYSize

    # get geotransform from inraster if not specified
    if geotransform is None:
        geotransform = inraster.GetGeoTransform()

    # get projection from inraster if not specified
    if projection is None:
        projection = inraster.GetProjection()

    # get number of bands from inraster if not specified
    if not numberofbands:
        numberofbands = inraster.RasterCount

    # create the new dataset using the parameters defined above
    newimage = create_new_raster(outpath, cols, rows, numberofbands,
                                 datatype, drivername,
                                 geotransform=geotransform,
                                 projection=projection,
                                 overwrite=overwrite)

    return newimage


def _slope_ritter(za, zb, cell_size=1, conversion_factor=1):
    """Ritter method to find difference in elevation over distance."""
    return (za - zb) / float(2 * cell_size * conversion_factor)


def _slope_horn(za, zb, zc, zd, ze, zf, cell_size=1, conversion_factor=1):
    """Horn method to find difference in elevation over distance."""
    return ((za + 2*zb + zc) - (zd + 2*ze + zf)) / \
                float(8 * cell_size * conversion_factor)


def _slope_calc(z, x_size, y_size,
                conversion_factor=1,
                percent_slope=False,
                method=DEFAULT_SLOPE_METHOD):
    """Calculates the slope of the center cell of a three-by-three array x.
    x is assumed to be passed in as a single-dimension array of size 9,
    such that the elements of x are equivalent to
    array([a, b, c, d, e, f, g, h, i]).

    Slope can be calculated using one of two methods (default is RITTER):

    1 -- Calculation of slope using the method from Ritter 1987 and
    Zevenbergen and Thorne 1987. Specifically, given a window such as:

     z0 | z1 | z2
    ----|----|----
     z3 | z4 | z5   then the slope w-e (dzdx) is (z5-z3) / 2*(cell_x_size) and
    ----|----|----   and the slope n-s (dzdy) is (z1-z7) / 2*(cell_y_size)
     z6 | z7 | z8

    Lui 2002 found Ritter to be the most accurate and least computationally-
    expensive slope calculation method.


    2 -- Calculation of slope using the method from Horn 1981.

    Specifically,

        slope w-e (dzdx) is ((z8+2*z5+z2) - (z6+2*z3+z0)) / 8*(cell_x_size)
        slope n-s (dzdy) is ((z2+2*z1+z0) - (z8+2*z7+z6)) / 8*(cell_y_size)

    ESRI uses this method for the spatial analyst slope calculation.


    In any case:
        To find the slope of z4 in degrees, find
            degrees(arctan(sqrt(dzdx**2 + dzdy**2))).

        To find the slope of z4 in percent rise, find
            sqrt(dzdx**2 / dzdy**2) * 100

    This function defaults to reporting the slope in degrees, but percent
    rise can be calculated by setting the percent_slope argument to True.

    Note: assumes units of elevation same as units of cell size. Provide a
    specific converison factor to convert (x, y) dimension to elevation units.
    """
    if method.upper() == "RITTER":
        dzdx = _slope_ritter(z[5], z[3], x_size, conversion_factor)
        dzdy = _slope_ritter(z[1], z[7], y_size, conversion_factor)

    elif method.upper() == "HORN":
        dzdx = _slope_horn(z[8], z[5], z[2], z[6], z[3], z[0],
                           x_size, conversion_factor)
        dzdy = _slope_horn(z[2], z[1], z[0], z[8], z[7], z[6],
                           y_size, conversion_factor)

    else:
        raise Exception("Slope calculation method is not recognized.")

    if percent_slope:
        return sqrt(dzdy**2 + dzdx**2) * 100
    else:
        return degrees(atan(sqrt(dzdx**2 + dzdy**2)))


def _aspect_calc(z, method=DEFAULT_SLOPE_METHOD, absolute_aspect=False):
    """Calculates the aspect of the center cell of a three-by-three array x.
    x is assumed to be passed in as a single-dimension array of size 9,
    such that the elements of x are equivalent to
    array([a, b, c, d, e, f, g, h, i]).

    Aspect can be calculated using one of same two methods presented for
    calculating slope above(default is RITTER).

    In any case, to find the aspect of z4:
        aspect = degrees(atan2(dzdy, -dzdx))

    If not using absolute aspect, aspect will be convered to compass directions
    (this is the default) via the following:

        if aspect < 0:
            aspect = 90.0 - aspect
        elif aspect > 90.0:
            aspect = 360.0 - aspect + 90.0
        else:
            aspect = 90.0 - aspect
    """
    if method.upper() == "RITTER":
        dzdx = _slope_ritter(z[5], z[3])
        dzdy = _slope_ritter(z[1], z[7])

    elif method.upper() == "HORN":
        dzdx = _slope_horn(z[8], z[5], z[2], z[6], z[3], z[0])
        dzdy = _slope_horn(z[2], z[1], z[0], z[8], z[7], z[6])

    else:
        raise Exception("Aspect calculation method is not recognized.")

    aspect = degrees(atan2(dzdy, -dzdx))

    if not absolute_aspect:
        if aspect < 0:
            aspect = 90.0 - aspect
        elif aspect > 90.0:
            aspect = 360.0 - aspect + 90.0
        else:
            aspect = 90.0 - aspect

    return aspect


def slope(array, x_size, y_size,
          conversion_factor=1,
          percent_slope=False,
          method=DEFAULT_SLOPE_METHOD):
    """Method uses scipy ndimage generic filter to do a moving window analysis
    on an input array to calculate a slope array.

    - x_size and y_size are the x and y cell dimensions, respectively
    - the conversion_factor is the coefficient to convert the horizontal units
          into the units of the cell values (e.g. 3.2808 to convert from
          meters to feet)
    - percent_slope is a bool indicating whether the output should be in
          percent rise (True), or in degrees (False, default)
    - method is the slope calculation method: options are RITTER (default)
          and HORN

    Returns an array of the same dimensions as the input.
    """
    return ndimage.generic_filter(array,
                                  _slope_calc,
                                  size=3,
                                  extra_arguments=(x_size,
                                                   y_size,
                                                   conversion_factor,
                                                   percent_slope,
                                                   method))


def aspect(array, method=DEFAULT_SLOPE_METHOD, absolute_aspect=False):
    """Method uses scipy ndimage generic filter to do a moving window analysis
    on an input array to calculate an aspect array.

    - absolute_aspect is a bool indicating whether the output directions
          should be in absolute directions (True), or in
          compass directions (False, default)
    - method is the slope calculation method: options are RITTER (default)
          and HORN

    Returns an array of the same dimensions as the input.
    """
    return ndimage.generic_filter(array,
                                  _aspect_calc,
                                  size=3,
                                  extra_arguments=(method, absolute_aspect))


# ********** MAIN **********

def main(elevation_raster,
         overwrite=False,
         conversion_factor=1,
         percent_slope=False,
         slope_method=DEFAULT_SLOPE_METHOD,
         slope_raster=None,
         aspect_raster=None,
         absolute_aspect=False,
         gdal_format=None):
    # open elevation raster and in data as array
    elevation_dataset = open_raster(elevation_raster)
    elevation_array = elevation_dataset.GetRasterBand(1).ReadAsArray()

    # get cell sizes
    geotransform = elevation_dataset.GetGeoTransform()
    x_cell_size, y_cell_size = geotransform[1], geotransform[5]

    # if slope raster calc slope
    if slope_raster:
        # create copy of elevation raster and get band
        slope_dataset = blank_raster_from_existing_raster(elevation_dataset,
                                                  slope_raster,
                                                  drivername=gdal_format,
                                                  datatype=gdal.GDT_Float32,
                                                  overwrite=overwrite)
        slope_band = slope_dataset.GetRasterBand(1)

        # calculate slope from elevation array
        slope_array = slope(elevation_array,
                            x_cell_size,
                            y_cell_size,
                            conversion_factor,
                            percent_slope,
                            slope_method)

        # write slope and close slope objects
        slope_band.WriteArray(slope_array)
        slope_band = None
        slope_dataset = None

    # if aspect_raster calc aspect
    if aspect_raster:
        # create copy for output and get band
        aspect_dataset = blank_raster_from_existing_raster(elevation_dataset,
                                                  aspect_raster,
                                                  drivername=gdal_format,
                                                  datatype=gdal.GDT_Int16,
                                                  overwrite=overwrite)
        aspect_band = aspect_dataset.GetRasterBand(1)

        # calculate the aspect from the elevation array
        aspect_array = aspect(elevation_array, slope_method, absolute_aspect)

        # write slope and close aspect objects
        aspect_band.WriteArray(aspect_array)
        aspect_band = None
        aspect_dataset = None

    # close elevation dataset
    elevation_dataset = None

    return 0


# ********** MAIN CHECK **********

if __name__ == '__main__':
    sys.exit(main(**parse_arguments(sys.argv[1:])))
