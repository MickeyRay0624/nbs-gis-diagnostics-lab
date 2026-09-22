# Your local NbS preparation package

1. Install **Python 3.12 (64-bit)** from https://www.python.org/downloads/ if it is not already installed. On Windows, select **Add Python to PATH**. Recommended: Windows 10/11 x64, or macOS 14+ Apple Silicon. Other environments need compatible binary wheels.
2. **Extract the entire ZIP** into a folder you can keep. Do not run files inside the ZIP.
3. Windows: double-click `Start Windows.bat`. macOS: open `Start macOS.command`. If macOS does not allow opening it, open Terminal, type `python3 ` (with a trailing space), drag `run.py` into the window, and press Return. On Linux, run `python3 run.py`.
4. The first run installs dependencies in this folder's `.venv`. Selected source data is downloaded and processed on your computer. Keep the terminal open. No code edits are required.
5. When finished, return to the website version that generated this package. Under **Import local results**, select `results.zip`. Choose a prepared module and select **Run diagnostic** to inspect its maps and area statistics.

`config.json` contains your selections. `aoi.geojson` contains your boundary. These files are checksum-linked. Change options by downloading a new package from the wizard.

## Accounts and cost

Flood, land degradation, land masks and climate data are public without an account. Groundwater and MODIS vegetation health require your own free NASA Earthdata account: https://urs.earthdata.nasa.gov/. Accept the NASA data application's authorisation if requested. The terminal prompts for login; passwords are not embedded in this package or results. The earthaccess library may use an existing login environment or netrc file. This script uses `persist=False` for new logins.

There is no platform compute server, cloud project, billing account or Google Earth Engine dependency. NASA's NCSS and OPeNDAP services supply spatially subset climate and groundwater files; all diagnostic calculations run locally. Internet, disk space and your computer's processing resources are still needed.

## Progress, size and restart

Start with a small area and Flood or Land degradation. Climate can involve hundreds of year/variable/model requests. Groundwater downloads regional daily GWS_tavg subsets on the native 0.25° grid; each file is checked for the requested date, coordinates and unit. MODIS downloads intersecting native HDF tiles. Long MODIS periods can require tens of GB or more. Long groundwater periods still need many daily requests. A fast connection does not remove provider limits.

Completed downloads, monthly indices and seasonal arrays are cached under `cache/`. Run the same launcher again to reuse them after interruption. Downloads resume at completed-file / request boundaries, not within an incomplete file. Keep the original package folder for resuming. Delete `cache/` to reclaim space when no longer needed.

The managed-download limit in the configuration applies to direct requests and NASA granules for this run. GDAL raster range requests and dependency installation are **not** included; this is not a hard total network or disk cap.

## Outputs

- `results.zip`: only the boundary, catalog, source provenance and prepared input GeoTIFFs required by the website. No credentials or raw downloads.
- `results/rasters/`: calculated numeric layers in GeoTIFF format.
- `results/statistics.csv`: area-weighted mean, extrema, eligible area, valid area and missing area for every output.
- `results/run-manifest.json`: configuration, periods, thresholds, sources, methods and limitations.
- `results/validation.json`: selected / available modules, failures and arithmetic results. This is not field validation or expert acceptance.
- `results/README.md`: per-module completion status and source links.

Failed modules remain explicitly unavailable. Completed modules can still be imported. Rerun to retry a provider outage or login failure. If a source version changed, update the toolkit rather than silently mixing releases.

## Scientific limits

Groundwater is modelled storage, not water-table depth. MODIS VHI is seasonal vegetation-health screening, **not FAO ASIS**. Climate uses NASA NEX-GDDP-CMIP6 **v2.0** and your selected model subset; model ranges are not confidence intervals. River-flood hazard is not a forecast or total flood risk. Land degradation combines published Trends.Earth components; it does not reproduce their upstream models. Every module retains its own scale, period, denominator and missing-data rules.

The fixed WorldCover 2021 mask approximates cropland or non-water area; it does not describe historical land use. Full-AOI mode has no land mask and must not be interpreted as crop-only or terrestrial-only statistics. Growing seasons and thresholds need local review.

The toolkit prepares five numeric modules. Land-cover change and forest fragmentation use the website's existing categorical GeoTIFF upload tools. Protection / OECM applicability, causal attribution and expert acceptance remain separate tasks.
