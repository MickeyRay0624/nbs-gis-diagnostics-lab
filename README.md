# NbS GIS Diagnostics Lab

A browser-based geospatial workspace for reproducible Nature-based Solutions diagnostics.

The repository also contains an installable Python GIS engine and command-line runner for deterministic LULC change processing. See [`engine/README.md`](engine/README.md).

A reproducible real-data technical demonstration uses the current Ganjam AOI with public ESA WorldCover rasters. See [`engine/examples/ganjam-worldcover-demo/README.md`](engine/examples/ganjam-worldcover-demo/README.md). Its 2020-2021 comparison demonstrates software behaviour only because the two WorldCover releases use different algorithm versions.

## Live demonstration

https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/

## What is real in the current prototype

- Ganjam District, Odisha, India as the study-area boundary
- 2021 ADM2 boundary geometry from geoBoundaries gbOpen
- Interactive OpenStreetMap basemap
- Automated geometry checks, area and vertex metrics, bounding box and provenance
- Downloadable AOI GeoJSON and machine-readable pre-flight manifest
- Python package with `nbs-gis preflight` and `nbs-gis run-lulc` commands
- Tested raster alignment, AOI masking, reclassification, area statistics and transition analysis

## What is not yet available

The project does not yet contain the approved 2002, 2012 and 2022 LULC rasters, a completed class crosswalk, fixed priority-area rules or reference outputs. The command-line preflight therefore reports the Ganjam example as blocked, and the interface does not present synthetic change values as scientific evidence.

## Data and map sources

- Boundary: [geoBoundaries gbOpen, India ADM2](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/), Open Data Commons Open Database License 1.0
- Basemap: [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors

## Local development

```bash
pnpm install
pnpm run dev
```

Create the production build:

```bash
pnpm run build
```

Changes pushed to `main` are deployed automatically through GitHub Pages.
