// NEX-GDDP-CMIP6 annual indices, native 0.25-degree grid.
// SSP2-4.5 baseline extension after 2014; future SSP2-4.5 and SSP5-8.5.
var all=ee.ImageCollection('NASA/GDDP-CMIP6');
function annual(model,scenario,year) {
  var start=ee.Date.fromYMD(year,1,1), end=start.advance(1,'year');
  var actualScenario=year<2015?'historical':scenario;
  var daily=all.filter(ee.Filter.eq('model',model)).filter(ee.Filter.eq('scenario',actualScenario)).filterDate(start,end).sort('system:time_start');
  var n=end.difference(start,'day');
  var valid=daily.select(['tas','tasmax','tasmin','pr']).count().reduce(ee.Reducer.min()).eq(n);
  var hot=daily.map(function(i){return i.select('tasmax').gt(308.15);}).sum().rename('hot_days');
  var warm=daily.map(function(i){return i.select('tasmin').gt(293.15);}).sum().rename('warm_nights');
  var frost=daily.map(function(i){return i.select('tasmin').lt(273.15);}).sum().rename('frost_days');
  var temp=daily.select('tas').mean().subtract(273.15).rename('mean_temperature');
  var wet=daily.map(function(i){return i.select('pr').multiply(86400).gt(100);}).sum().rename('heavy_rain_days');
  var dry=daily.select('pr').toArray().multiply(86400).lt(1);
  var dryTotal=dry.arrayReduce(ee.Reducer.sum(),[0]).arrayGet([0,0]);
  var starts=dry.arraySlice(0,1).and(dry.arraySlice(0,0,-1).not()).arrayReduce(ee.Reducer.sum(),[0]).arrayGet([0,0]).add(dry.arrayGet([0,0]));
  var spell=dryTotal.divide(starts.max(1)).rename('mean_dry_spell');
  return ee.Image.cat([hot,warm,frost,temp,wet,spell]).updateMask(valid).set('system:index','y'+year).toFloat();
}
['ACCESS-CM2','MIROC6','MPI-ESM1-2-HR'].forEach(function(model){
  [['ssp245',[1991,2001,2011,2040,2050,2060]],['ssp585',[2040,2050,2060]]].forEach(function(config){
    config[1].forEach(function(first){
      var images=[];for(var y=first;y<first+10;y++)images.push(annual(model,config[0],y));
      var label='CLIMATE_'+model+'_'+config[0]+'_'+first;
      ee.ImageCollection(images).toBands().unmask(-9999).toFloat().getDownloadURL({
        name:label,format:'GEO_TIFF',filePerBand:false,crs:'EPSG:4326',
        crs_transform:[0.25,0,84,0,-0.25,20.5],dimensions:[5,7]},function(url,error){print(label,url||error);});
    });
  });
});
print('Source versions',all.filter(ee.Filter.inList('model',['ACCESS-CM2','MIROC6','MPI-ESM1-2-HR'])).filterDate('1991-01-01','2070-01-01').aggregate_histogram('version'));
