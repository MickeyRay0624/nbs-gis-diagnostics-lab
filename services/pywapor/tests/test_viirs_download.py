from pathlib import Path

import netCDF4
import numpy as np
import pytest

from online.viirs_download import download_geolocation, native_geolocation_url


BASE = 'https://ladsweb.modaps.eosdis.nasa.gov/opendap/RemoteResources/laads/allData/5200/VNP03IMG/2021/001/VNP03IMG.A2021001.0730.002.2021124105140.nc'
QUERY = '?dap4.ce=/geolocation_data/longitude%5B%5D%5B%5D;/geolocation_data/latitude%5B%5D%5B%5D'


def test_only_full_geolocation_requests_use_native_source():
    assert native_geolocation_url(BASE + '.dap.nc4' + QUERY) == BASE.replace('/opendap/RemoteResources/laads/', '/archive/')
    assert native_geolocation_url(BASE + '.dap.nc4' + QUERY.replace('%5B%5D', '%5B0:1:3%5D')) is None
    assert native_geolocation_url(BASE.replace('https:', 'http:') + '.dap.nc4' + QUERY) is None
    assert native_geolocation_url(BASE.replace('ladsweb.modaps.eosdis.nasa.gov', 'example.org') + '.dap.nc4' + QUERY) is None


def test_range_download_preserves_native_coordinates_and_attributes(tmp_path):
    original = tmp_path / 'original.nc'
    with netCDF4.Dataset(original, 'w') as ds:
        ds.createDimension('number_of_lines', 11)
        ds.createDimension('number_of_pixels', 13)
        group = ds.createGroup('geolocation_data')
        for name in ('latitude', 'longitude'):
            var = group.createVariable(name, 'i2', ('number_of_lines', 'number_of_pixels'), fill_value=-32768, zlib=True)
            var.scale_factor = 0.01
            var.units = 'degrees_north' if name == 'latitude' else 'degrees_east'
            var.set_auto_maskandscale(False)
            values = np.arange(143, dtype='int16').reshape(11, 13)
            values[0, 0] = -32768
            var[:] = values
        group.createVariable('unused', 'f4', ('number_of_lines', 'number_of_pixels'))[:] = 7
    body = original.read_bytes()
    ranges = []

    class Response:
        status_code = 206
        def __init__(self, start, stop):
            self.content = body[start:stop]
            self.headers = {'Content-Range': f'bytes {start}-{stop-1}/{len(body)}'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def close(self): pass
        def raise_for_status(self): pass
        def iter_content(self, _):
            yield self.content

    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, headers, stream):
            assert stream and headers['Accept-Encoding'] == 'identity'
            start, last = map(int, headers['Range'].removeprefix('bytes=').split('-'))
            ranges.append((start, last+1))
            return Response(start, last+1)

    target = tmp_path / 'prepared.nc'
    download_geolocation('fixture', target, Session(), Session)
    assert len(ranges) == 5
    assert sorted(ranges[1:]) == [(len(body)*i//4, len(body)*(i+1)//4) for i in range(4)]
    with netCDF4.Dataset(original) as a, netCDF4.Dataset(target) as b:
        assert set(b.groups['geolocation_data'].variables) == {'latitude', 'longitude'}
        for name in ('latitude', 'longitude'):
            before, after = a.groups['geolocation_data'].variables[name], b.groups['geolocation_data'].variables[name]
            np.testing.assert_array_equal(before[:].data, after[:].data)
            np.testing.assert_array_equal(before[:].mask, after[:].mask)
            assert {k: before.getncattr(k) for k in before.ncattrs()} == {k: after.getncattr(k) for k in after.ncattrs()}
    assert not list(tmp_path.glob('*.tmp'))

    target.unlink()
    original_iter = Response.iter_content
    Response.iter_content = lambda self, _: iter([self.content[:-1]])
    with pytest.raises(RuntimeError, match='incomplete'):
        download_geolocation('fixture', target, Session(), Session)
    assert not target.exists() and not list(tmp_path.glob('*.tmp'))
    Response.iter_content = original_iter
    Response.status_code = 200
    with pytest.raises(RuntimeError, match='requested VIIRS byte range'):
        download_geolocation('fixture', target, Session(), Session)
    assert not target.exists()
