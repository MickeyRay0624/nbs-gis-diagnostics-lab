// Run in the Code Editor using a registered noncommercial project.
// Seasonal MODIS inputs, not FAO ASIS. Each export is one crop-start year.
var crs = 'PROJCS["WGS 84 / NSIDC EASE-Grid 2.0 Global",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Cylindrical_Equal_Area"],PARAMETER["standard_parallel_1",30],PARAMETER["central_meridian",0],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","6933"]]';
var ndvi = ee.ImageCollection('MODIS/061/MOD13A2').map(function(i) {
  return i.select('NDVI').multiply(0.0001).updateMask(i.select('SummaryQA').lte(1)).copyProperties(i,['system:time_start']);
});
var lst = ee.ImageCollection('MODIS/061/MOD11A2').map(function(i) {
  var qa=i.select('QC_Day');
  return i.select('LST_Day_1km').multiply(0.02).subtract(273.15)
    .updateMask(qa.bitwiseAnd(3).eq(0).and(qa.rightShift(6).bitwiseAnd(3).lte(1)))
    .copyProperties(i,['system:time_start']);
});
function season(collection,start,end,name) {
  var selected=collection.filterDate(start,end);
  return selected.mean().rename(name).addBands(selected.count().divide(selected.size()).multiply(100).rename(name+'_coverage'));
}
for(var y=2001;y<=2023;y++) {
  (function(year) {
    var kh=ee.Date.fromYMD(year,6,1),khEnd=ee.Date.fromYMD(year,11,1);
    var ra=ee.Date.fromYMD(year,11,1),raEnd=ee.Date.fromYMD(year+1,4,1);
    var out=season(ndvi,kh,khEnd,'K_NDVI').addBands(season(lst,kh,khEnd,'K_LST'))
      .addBands(season(ndvi,ra,raEnd,'R_NDVI')).addBands(season(lst,ra,raEnd,'R_LST')).unmask(-9999).toFloat();
    out.getDownloadURL({name:'modis_'+year,format:'GEO_TIFF',filePerBand:false,crs:crs,
      crs_transform:[1000,0,8121000,0,-1000,2536000],dimensions:[99,164]},
      function(url,error){print('MODISQA_'+year,url||error);});
  })(y);
}
