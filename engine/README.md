# NbS GIS processing engine

This package provides deterministic command-line processing for the first NbS GIS automation slice: land-use and land-cover change inside an approved area of interest.

Version 0.1 accepts already-classified categorical rasters. It does not classify raw satellite imagery and it does not generate priority areas until the grid and significance rules are approved by the GIS team.

## Install

From the repository root:

```bash
python3 -m venv .venv-engine
source .venv-engine/bin/activate
python -m pip install --upgrade pip
python -m pip install -e './engine[test]'
```

## Commands

Validate all inputs without starting analysis:

```bash
nbs-gis preflight --config engine/examples/ganjam/config.yml
```

Run the deterministic LULC processing after preflight passes:

```bash
nbs-gis run-lulc --config engine/examples/ganjam/config.yml
```

Use `--run-id NAME` when a stable run identifier is required. Existing run directories are never overwritten.

## Processing contract

The pipeline performs the following operations:

1. Validate the AOI geometry and declared CRS.
2. Validate every raster, the crosswalk and the target-grid safety limit.
3. Reproject categorical rasters with nearest-neighbour resampling.
4. Clip to the AOI and reclassify source classes through a CSV crosswalk.
5. Calculate class areas for each year.
6. Create binary change rasters and class-to-class transition rasters and tables.
7. Create map PNGs, a data-derived draft summary, a QA report and a provenance manifest.

The default target CRS is EPSG:6933, a global equal-area CRS with metre units. Input rasters can use different CRSs or grids; the engine aligns them to one approved target grid before comparison.

## Crosswalk schema

The CSV crosswalk requires four columns:

```csv
source_code,target_code,target_name,color
10,1,Cropland,#e4bf61
20,2,Forest,#2f6d45
```

Target codes must be integers from 1 to 999. Each source code can appear once. Repeated target codes are allowed when multiple detailed source classes map to one project class, but their name and colour must agree.

## Output structure

Each successful execution writes a new immutable run directory:

```text
outputs/<run-id>/
  input_config.yml
  preflight_report.json
  run_manifest.json
  qa_report.json
  summary.json
  diagnostic_summary.md
  rasters/
    lulc_<year>_reclassified.tif
    change_<start>_<end>.tif
    transition_<start>_<end>.tif
  tables/
    class_area_by_year.csv
    transition_<start>_<end>_long.csv
    transition_<start>_<end>_matrix.csv
  maps/
    lulc_<year>.png
    change_<start>_<end>.png
```

Every released result must still pass GIS expert review. The manifest records source hashes, software versions, configuration, warnings and limitations so that a run can be reproduced and audited.

## Tests

The tests generate small temporary GeoTIFF fixtures with known results. They are software tests only and are never presented as project evidence.

```bash
ruff check engine/src engine/tests
pytest engine/tests
```
