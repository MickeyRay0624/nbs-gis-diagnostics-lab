# NbS GIS Diagnostics Lab

A browser-based geospatial workspace for reproducible Nature-based Solutions diagnostics.

## Live demonstration

https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/

## What is real in the current prototype

- Ganjam District, Odisha, India as the study-area boundary
- 2021 ADM2 boundary geometry from geoBoundaries gbOpen
- Interactive OpenStreetMap basemap
- Automated geometry checks, area and vertex metrics, bounding box and provenance
- Downloadable AOI GeoJSON and machine-readable pre-flight manifest

## What is not yet available

The project does not yet contain the 2002, 2012 and 2022 LULC rasters, a class crosswalk, a fixed processing specification or reference outputs. The interface therefore keeps land-cover change analysis locked and does not present synthetic change values as scientific evidence.

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
