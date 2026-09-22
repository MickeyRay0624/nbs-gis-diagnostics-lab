import hashlib

import pytest

from online.source_audit import acquired_manifest, required_products


def test_missing_thermal_source_cannot_silently_continue(tmp_path):
    configuration = {
        'bt': {'products': [{'source': 'VIIRSL1', 'product_name': 'VNP02IMG'}]},
        'ndvi': {'products': [{'source': 'SENTINEL2', 'product_name': 'S2MSI2A_R60m'}]},
        'se_root': {'products': [{'source': 'FILE:{folder}/se_root_out*.nc', 'product_name': 'none'}]},
    }
    required = required_products(configuration)
    # The expected source set survives the upstream removal of a failed source.
    configuration['bt']['products'].clear()
    assert len(required) == 2
    optical = tmp_path / 'SENTINEL2.nc'
    optical.write_bytes(b'fixture optical input')
    inputs = {('SENTINEL2', 'S2MSI2A_R60m'): str(optical)}
    with pytest.raises(RuntimeError, match='could not be acquired'):
        acquired_manifest(tmp_path, required, inputs)
    thermal = tmp_path / 'VIIRSL1.nc'
    thermal.write_bytes(b'fixture thermal input')
    inputs[('VIIRSL1', 'VNP02IMG')] = str(thermal)
    result = acquired_manifest(tmp_path, required, inputs)
    assert len(result['files']) == 2
    assert result['files'][1] == {'source': 'VIIRSL1', 'product': 'VNP02IMG', 'path': 'VIIRSL1.nc',
                                  'bytes': 21, 'sha256': hashlib.sha256(b'fixture thermal input').hexdigest()}
    assert str(tmp_path) not in str(result)


def test_empty_or_external_source_is_not_published(tmp_path):
    empty = tmp_path / 'empty.nc'
    empty.touch()
    required = frozenset({('SENTINEL2', 'S2MSI2A_R60m')})
    with pytest.raises(RuntimeError, match='empty'):
        acquired_manifest(tmp_path, required, {next(iter(required)): str(empty)})
    with pytest.raises(ValueError):
        acquired_manifest(tmp_path / 'model', required, {next(iter(required)): str(empty)})
