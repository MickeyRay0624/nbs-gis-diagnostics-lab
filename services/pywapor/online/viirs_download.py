"""Read the same VIIRS geolocation arrays from the compressed NASA source file."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit


def native_geolocation_url(url):
    parts = urlsplit(url)
    prefix = '/opendap/RemoteResources/laads/'
    query = parse_qs(parts.query)
    expected = {'/geolocation_data/longitude[][]', '/geolocation_data/latitude[][]'}
    if (parts.scheme != 'https' or parts.netloc != 'ladsweb.modaps.eosdis.nasa.gov'
            or parts.fragment or set(query) != {'dap4.ce'} or len(query['dap4.ce']) != 1
            or set(query['dap4.ce'][0].split(';')) != expected
            or not re.fullmatch(prefix + r'allData/5200/VNP03IMG/\d{4}/\d{3}/VNP03IMG\.[A-Za-z0-9.]+\.nc\.dap\.nc4', parts.path)):
        return None
    return 'https://' + parts.netloc + '/archive/' + parts.path[len(prefix):-len('.dap.nc4')]


def _range(session, url, start, stop, size=None):
    response = session.get(url, headers={'Range': f'bytes={start}-{stop-1}', 'Accept-Encoding': 'identity'}, stream=True)
    try:
        response.raise_for_status()
        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
        if (response.status_code != 206 or not match or tuple(map(int, match.groups()[:2])) != (start, stop-1)
                or (size is not None and int(match.group(3)) != size)):
            raise RuntimeError('NASA did not return the requested VIIRS byte range.')
    except BaseException:
        response.close()
        raise
    return response, int(match.group(3))


def download_geolocation(url, filename, session, session_factory):
    """Four bounded HTTP ranges, then lossless copying of the two native arrays."""
    import netCDF4

    target = Path(filename)
    if target.is_file():
        return str(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    source, prepared = Path(str(target) + '.native.tmp'), Path(str(target) + '.geo.tmp')
    response, size = _range(session, url, 0, 8)
    with response:
        if response.content != b'\x89HDF\r\n\x1a\n' or not 8 < size <= 512 * 1024**2:
            raise RuntimeError('The VIIRS geolocation source is invalid or too large.')
    try:
        with source.open('w+b') as file:
            file.truncate(size)
            fd = file.fileno()

            def part(index):
                start, stop = size * index // 4, size * (index+1) // 4
                position = start
                with session_factory() as connection:
                    response, _ = _range(connection, url, start, stop, size)
                    with response:
                        for block in response.iter_content(1024 * 1024):
                            if position + len(block) > stop:
                                raise RuntimeError('The VIIRS byte range exceeds its declared size.')
                            remaining = memoryview(block)
                            while remaining:
                                written = os.pwrite(fd, remaining, position)
                                if written <= 0:
                                    raise OSError('Could not write the VIIRS source file.')
                                position += written
                                remaining = remaining[written:]
                if position != stop:
                    raise RuntimeError('The VIIRS byte range is incomplete.')

            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(part, range(4)))

        with netCDF4.Dataset(source) as incoming, netCDF4.Dataset(prepared, 'w', format='NETCDF4') as outgoing:
            group = incoming.groups['geolocation_data']
            latitude, longitude = (group.variables[name] for name in ('latitude', 'longitude'))
            if latitude.ndim != 2 or latitude.shape != longitude.shape or latitude.dimensions != longitude.dimensions:
                raise RuntimeError('The VIIRS geolocation grid is inconsistent.')
            for dimension, length in zip(latitude.dimensions, latitude.shape):
                outgoing.createDimension(dimension, length)
            result = outgoing.createGroup('geolocation_data')
            result.setncatts({key: group.getncattr(key) for key in group.ncattrs()})
            for name in ('latitude', 'longitude'):
                variable = group.variables[name]
                variable.set_auto_maskandscale(False)
                options = {'fill_value': variable.getncattr('_FillValue')} if '_FillValue' in variable.ncattrs() else {}
                copied = result.createVariable(name, variable.dtype, variable.dimensions, zlib=True, complevel=1, **options)
                copied.setncatts({key: variable.getncattr(key) for key in variable.ncattrs() if key != '_FillValue'})
                copied.set_auto_maskandscale(False)
                # Bound RAM and preserve every original coordinate; no spatial
                # sampling, interpolation or change to the thermal/QA arrays.
                for row in range(0, variable.shape[0], 128):
                    copied[row:row+128, :] = variable[row:row+128, :]
        prepared.replace(target)
    finally:
        source.unlink(missing_ok=True)
        prepared.unlink(missing_ok=True)
    return str(target)


def configure_geolocation_download(viirs, session_factory):
    original = viirs.download_url

    def download_url(url, fp, session=None, **kwargs):
        native = native_geolocation_url(url)
        if native is None:
            return original(url, fp, session=session, **kwargs)
        if session is None:
            raise RuntimeError('An authenticated NASA data session is required.')
        return download_geolocation(native, fp, session, session_factory)

    viirs.download_url = download_url
