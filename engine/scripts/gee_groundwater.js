// Run in the Earth Engine Code Editor with your registered project selected.
// Source: NASA GLDAS 2.2, GWS_tavg (mm), native 0.25-degree grid.
// January 2003 is unavailable in this collection and is not fabricated.
var groundwater = ee.ImageCollection('NASA/GLDAS/V022/CLSM/G025/DA1D').select('GWS_tavg');
var region = ee.Geometry.Rectangle([84, 18.75, 85.25, 20.5], null, false);
function exportYear(year) {
  var months = ee.List.sequence(year === 2003 ? 2 : 1, 12).map(function(month) {
    var start = ee.Date.fromYMD(year, month, 1), end = start.advance(1, 'month');
    var days = groundwater.filterDate(start, end);
    return days.mean().updateMask(days.count().gte(end.difference(start, 'day').multiply(0.9)))
      .rename('GWS').set('system:index', start.format('YYYY_MM'));
  });
  ee.ImageCollection.fromImages(months).toBands().toFloat().unmask(-9999).getDownloadURL({
    name: 'ganjam_gldas_' + year, format: 'GEO_TIFF', filePerBand: false,
    crs: 'EPSG:4326', crs_transform: [0.25, 0, 84, 0, -0.25, 20.5], region: region
  }, function(url, error) { print('GW_' + year, url || error); });
}
for (var year = 2003; year <= 2023; year++) exportYear(year);
