Demo 1
======


**Scenario**

We work for a small municipality that experiences strong windstorms,
and the city is on a push to increase disaster preparedness of its
residents. One part of this program is to identify potential hazards
to residents, namely large trees that have the potential to cause
significant damage to homes in the city bounds. The city has cataloged
all trees in its jurisdiction, including each tree's height. In addition
to these tree points, the city also maintains building and zoning datasets
in its GIS layers.

Our task is to perform this analysis to identify residential buildings also
within the hazard area of large trees. We know that this analysis is likely
to be repeated, perhaps with different tree heights or different zoing
classifications, so we need to make a generalized and efficient way to
run it again in the future. Thus, we have determined that a python script
needs to be developed, rather than running this analysis manually by hand.
In developing the script, we will need to ensure that the zoning classifications
and large tree threshold height can be easily changed to accommodate changing
analysis requirements.

Lastly, per the recent declaration of the city GIS Manager, all current analyses
must be performed with data from a file geodatabase. However, all our data sources
are still in shapefile format. Consequently, we will need to import all our data
into a file geodatabase before performing the analysis. For organization, the data
must be placed in a feature dataset named Data in the geodatabase, and any result
feature classes must go into a feature dataset called Results. All our data and
results should be in the Oregon State Plane North reference system with the
NAD 1983 HARN datum and units in international feet (EPSG 2913). Unfortunately,
we know last summer we had an incompetent intern who couldn't keep his datums
straight, and our data may not all be in the correct reference system.


**Included Files**

This repo includes the following files and folder:

- demo1.py -- the python script written for this demo
- data.mxd -- a ArcMap document displaying all the data layers so
  we can see with what data we are working
- data/ -- a folder containing shapefile data for this analysis
