// GLC-FCS30D annual bands b1–b23 represent 2000–2022.
// A 50 m equal-area browser grid; original source resolution is 30 m.
var region = ee.Geometry.Rectangle([84.16,18.93,85.19,20.29], null, false);
var annual = ee.ImageCollection('projects/sat-io/open-datasets/GLC-FCS30D/annual')
  .filterBounds(region).mosaic();
var land = annual.select(['b3','b13','b23'], ['LULC2002','LULC2012','LULC2022']);
land = land.updateMask(land.neq(250)).unmask(0).toUint8();
land.getDownloadURL({name:'ganjam_glcfcs', format:'GEO_TIFF', filePerBand:false,
  crs:"PROJCS[\"WGS 84 / NSIDC EASE-Grid 2.0 Global\",GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563,AUTHORITY[\"EPSG\",\"7030\"]],AUTHORITY[\"EPSG\",\"6326\"]],PRIMEM[\"Greenwich\",0,AUTHORITY[\"EPSG\",\"8901\"]],UNIT[\"degree\",0.0174532925199433,AUTHORITY[\"EPSG\",\"9122\"]],AUTHORITY[\"EPSG\",\"4326\"]],PROJECTION[\"Cylindrical_Equal_Area\"],PARAMETER[\"standard_parallel_1\",30],PARAMETER[\"central_meridian\",0],PARAMETER[\"false_easting\",0],PARAMETER[\"false_northing\",0],UNIT[\"metre\",1,AUTHORITY[\"EPSG\",\"9001\"]],AXIS[\"Easting\",EAST],AXIS[\"Northing\",NORTH],AUTHORITY[\"EPSG\",\"6933\"]]", crs_transform:[50,0,8121050,0,-50,2535150], dimensions:[1962,3237]},
  function(url,error){print('GLC_DOWNLOAD',url||error);});
print('Source tiles',ee.ImageCollection('projects/sat-io/open-datasets/GLC-FCS30D/annual').filterBounds(region).aggregate_array('system:index').join(', '));
