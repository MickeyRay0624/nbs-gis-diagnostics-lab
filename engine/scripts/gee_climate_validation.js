// Independent NumPy validation inputs: normal/leap years, half-year chunks
// stay below the 1024-band synchronous-download limit.
[1991,1992].forEach(function(year){[1,7].forEach(function(month){
 var start=ee.Date.fromYMD(year,month,1),end=start.advance(6,'month');
 var daily=ee.ImageCollection('NASA/GDDP-CMIP6').filter(ee.Filter.eq('model','ACCESS-CM2')).filter(ee.Filter.eq('scenario','historical')).filterDate(start,end).sort('system:time_start').select(['tasmax','tasmin','tas','pr']);
 daily.toBands().unmask(-9999).toFloat().getDownloadURL({name:'daily_'+year+'_'+month,format:'GEO_TIFF',filePerBand:false,crs:'EPSG:4326',crs_transform:[0.25,0,84,0,-0.25,20.5],dimensions:[5,7]},function(url,error){print('DAILY_'+year+'_'+month,url||error);});
});});
['ACCESS-CM2','MIROC6','MPI-ESM1-2-HR'].forEach(function(model){
 var c=ee.ImageCollection('NASA/GDDP-CMIP6').filter(ee.Filter.eq('model',model)).filterDate('1991-01-01','2070-01-01');
 ee.Dictionary({license:c.aggregate_histogram('license'),version:c.aggregate_histogram('version'),interpolated:c.aggregate_histogram('interpolated')}).evaluate(function(v,error){print(model+' provenance',error||JSON.stringify(v));});
});
