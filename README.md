# NbS GIS Diagnostics Lab

A browser workspace for land-cover change and forest fragmentation. Open the [live workspace](https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/), choose a module and click **Run analysis**. Computation runs locally in a Web Worker; GitHub Pages does not need a Python server and uploaded files are not sent to a service.

## Available in the page

- A persistent study-area overview with the selected boundary, a location label, fit/context controls and automatic uploaded-raster footprint preview. Running analysis keeps the map and its current view in place.
- An English feature guide explains every control, calculation, metric and export. Open **Guide** in the header or read the [full guide](public/guide.en.md).
- A ready-to-run Ganjam example with real ESA WorldCover 2020 v100 and 2021 v200 inputs.
- Configurable years: 2–3 periods for LULC, 1–3 for the independent forest module.
- Single-band GeoTIFF upload, nearest-neighbour alignment to a common EPSG:6933 equal-area grid, and optional polygon AOI masking.
- WorldCover and ESRI class presets; GLC-FCS30D or other rasters can import their observed codes, then use a CSV crosswalk for class names, colours and aggregation. These are local uploads, not authenticated Earth Engine connections.
- An editable crosswalk and selectable forest classes; configurable grid size, forest edge width and AOI boundary treatment.
- Land-cover maps, pairwise class-difference maps, transition matrices and gross gains/losses/net change on the **common valid footprint**.
- Forest core, edge, patch and internal-clearing maps, with area, patch count, edge density, shape, mean patch size and largest-patch metrics.
- Optional protected-area and OECM GeoJSON or zipped Shapefile uploads. Protected areas take precedence over OECMs in overlap. Without protection data only `All` is reported.
- Downloads: map PNGs with legends, analysis GeoTIFFs, class-area/transition/gain-loss/forest-metric CSVs, crosswalk CSV and a JSON run manifest with input hashes, parameters and QA.

## Start with public data

The example uses the gbOpen Ganjam district boundary and public WorldCover tile `N18E084`. Original 10 m classes were resampled by nearest neighbour onto a **50 m** EPSG:6933 grid and masked to the AOI. The two compressed inputs total approximately 1.3 MB. The example does not contain protected-area or OECM evidence.

WorldCover **2020 and 2021 use different algorithm versions**. Their apparent differences combine algorithm and real land-cover differences; this is a software demonstration, not a verified land-cover change assessment. Coarser resampling affects fragmentation; a 50 m edge is only one cell on the default test grid. Project decisions require suitable source data, a reviewed forest definition, and GIS validation.

[Input provenance](public/data/worldcover/metadata.json) · [Independent Python reference](public/data/worldcover/python-reference.json) · [Cross-language validation](public/data/worldcover/validation.json) · [Validation notes](docs/validation.md)

## Upload contract

- North-up, PixelIsArea, single-band categorical GeoTIFFs with integer class codes 1–65534. **Code 0 and the declared GeoTIFF NoData value are excluded.** Recode valid zero-valued classes before upload. RGB satellite images are not classified by this tool.
- Supported input CRSs: EPSG:4326, EPSG:3857, EPSG:6933 and WGS84 UTM north/south zones. Outputs always use EPSG:6933, square cells and nearest-neighbour pixel-centre sampling.
- Source rasters: at most 100 MB/file and 25 million pixels. Analysis: at most 8 million cells. Use cropped GeoTIFFs for full-resolution source products; smaller requested cells cannot recover detail absent from an input.
- AOI/protection: polygon WGS84 GeoJSON, or a ZIP with one Shapefile layer including `.shp`, `.dbf`, `.shx` and `.prj`. Vector upload limit: 25 MB. GeoJSON coordinates must lie between 85°S and 85°N. The earliest-year raster's extent is used if no AOI is supplied.
- Crosswalk CSV columns: `source_code,target_code,target_name,color`. Target codes are 1–999. Merged classes must use identical target names and `#RRGGBB` colours. Unknown source codes block the run. ESRI clouds remain a source class; mask unreliable observations before analysis.
- Years must be distinct. Missing files, invalid grids, unmapped classes, invalid forest definitions, edge widths below one cell and empty comparison footprints produce actionable errors. Changing settings clears old results; a running job can be cancelled.

## Forest method

The supplied SCALA ArcPy workflow is the reference for the standalone [Python module](engine/src/nbs_gis/fragmentation.py) and [browser implementation](src/analysis/compute.ts). Neither implementation requires ArcGIS.

1. Build a binary forest mask from selected target classes.
2. Identify eight-connected forest patches over the whole valid AOI. Protection polygons never split the forest before classification.
3. Use exact Euclidean pixel-centre distance to known non-forest. Core is strictly farther than the chosen edge width. Patches with no core are classified as `Patch`; remaining non-core forest is `Edge`.
4. Internal clearings are four-connected, enclosed **non-forest** components. Components touching NoData or the grid perimeter are excluded. Clearings are not added to forest area. This follows the supplied script's *clearing* meaning; it is not the “perforated forest” class of other fragmentation tools.
5. Administrative/NoData boundaries do not create edges by default. An explicit option counts them. All-forest landscapes with ignored boundaries have no observed ecological edge.
6. Stratify only after classification. Class area and ecological edge length are allocated pixel by pixel. NP, MPS, MSI, AWMSI and MPE use whole patches assigned by majority area (ties: Protected, OECM, Unprotected). MPS uses the actual mean area of assigned whole patches. LPI uses the largest patch's **intersection** with the stratum divided by stratum landscape area; it cannot exceed 100%.

Cross-boundary patch counts are recorded. A stratum can contain forest portions without owning a whole patch; its NP can therefore be zero. Clearing intersection counts need not sum to the whole-landscape count. Ignoring administrative edges also reduces perimeters used by shape metrics. “Unprotected” means outside the supplied polygons; their completeness and historical validity are not inferred.

## Local development and validation

MapLibre 6's separate ESM worker is imported with Vite's `?worker&url` and registered before creating maps. This bundles its shared dependency and preserves the GitHub Pages base path. Without this, raster basemap tiles can render while the GeoJSON boundary silently fails. See the [official Vite integration](https://github.com/maplibre/maplibre-gl-js/blob/main/docs/index.md#esm).

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm test
pnpm run test:demo
pnpm build
```

The frontend tests include hand-calculated forests, NoData, Euclidean distances, class crosswalks, GeoTIFF round trips, uploaded three-period data and protection/OECM overlaps. `test:demo` compares the actual browser computation code with Python/SciPy results: 91 numeric values and all 12,701,988 fragmentation cells across the two public rasters.

For the Python package and configurable batch workflow, see [engine/README.md](engine/README.md). To rebuild public inputs from the original downloaded tiles:

```bash
bash engine/examples/ganjam-worldcover-demo/download_data.sh
.venv-engine/bin/python engine/scripts/prepare_web_demo.py
pnpm run test:demo
```

Only cropped open inputs and non-sensitive provenance are published. Original tiles and full local run manifests remain in ignored directories. Pushes to `main` build, test and deploy through GitHub Pages.

## Sources

- [ESA WorldCover data access and licence](https://esa-worldcover.org/en/data-access), CC BY 4.0. [2020 v100](https://doi.org/10.5281/zenodo.5571936), [2021 v200](https://doi.org/10.5281/zenodo.7254221).
- © ESA WorldCover project 2020/2021 / Contains modified Copernicus Sentinel data processed by ESA WorldCover consortium.
- [geoBoundaries gbOpen, India ADM2](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/), boundary represented year 2021, ODbL 1.0. This is the pilot boundary, pending project acceptance.
- [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), basemap.
- [GLC-FCS30D product paper and dataset](https://essd.copernicus.org/articles/16/1353/2024/), for user-supplied GLC-FCS30D workflows.
