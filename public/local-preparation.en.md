# Prepare another study area on your own computer

**Version 0.5.0-dev · local development · 16 September 2026**

This version adds a website configuration wizard and a portable Python toolkit. It has not been deployed to the public GitHub Pages website. The existing Ganjam example remains available in the local workspace.

## Quick start

1. Select **Create Python package** near the top of the page.
2. Enter a study-area name. Use the Ganjam example, upload a WGS84 GeoJSON polygon/multipolygon, or enter a rectangle. Confirm the boundary on the preview map. Choose **Use small Bhubaneswar test area** for a short first trial.
3. Choose diagnostics and their options. **River flood hazard** and **Land degradation** are selected initially because they use public raster windows and need no account.
4. Review the package and select your operating system. Select **Download Python package**.
5. Install Python 3.12 (64-bit) once if needed, then **extract the entire ZIP**. On Windows select “Add Python to PATH” during installation. Open `Start Windows.bat` or `Start macOS.command`. The first run creates `.venv` in that folder and installs the required libraries. The included README explains a Terminal alternative if macOS blocks the launcher.
6. Keep the terminal open while files download and calculations run. When finished, use **Import local results** on the website and select `results.zip` from the extracted folder.
7. The overview changes to the package's boundary. Select a prepared diagnostic and **Run diagnostic**. Review maps, coverage, source resolution, methods and exports.

No code editing, Cloud Project ID or Earth Engine registration is needed. Python installation is still a one-time prerequisite. Target systems are Windows 10/11 x64 and macOS 14+ Apple Silicon with Python 3.12; this development build was executed on macOS Apple Silicon. Windows has not yet been tested end to end. Other systems require compatible binary Python packages.

## What can be selected

| Diagnostic | Website choices | Public data and calculation |
| --- | --- | --- |
| River flood hazard | 10-, 100-, 500-year return periods | JRC / CEMS-GloFAS v2.1.2 native 3-arc-second depth tiles. Automatically select intersecting tiles, keep positive depths, exclude permanent water and spurious-depth flags. NoData is not interpreted as zero risk. |
| Land degradation | Fixed published periods; eligible-area mask | Trends.Earth SDG 15.3.1 v1.2 published productivity, land-cover and modelled SOC components. Reclassify and combine using one-out-all-out. Baseline 2000–2015; latest productivity 2008–2023 and land cover/SOC 2015–2022 in the 2023 assessment. SOC integer values exactly ±10% are unknown because of rounding. |
| Climate extremes | Baseline and future years; 1–3 models; SSP2-4.5 / SSP5-8.5; six indices; temperature/rain thresholds | NASA NEX-GDDP-CMIP6 v2.0 daily 0.25° files supplied through official NCCS spatial-subset requests. Calculate annual counts, mean temperature and longest within-year dry spell locally, then period/model means and future-minus-baseline changes. Every daily observation, selected year and model must be valid for the corresponding mean. Model minimum/maximum changes are not confidence intervals. |
| Groundwater | Nonoverlapping baseline and monitoring years, 2003–2025 | NASA GLDAS 2.2 daily GWS_tavg regional OPeNDAP subsets at the native 0.25° resolution; dates, coordinates and units are checked. Monthly means require 90% of expected days; annual/period means require 90% of months. Equal-month weighting and annual Theil–Sen trend with at least 90% valid years. January 2003 is unavailable. Storage is not well depth. |
| Drought & vegetation | At least 15 reference years; two comparison years; one or two nonoverlapping growing seasons | NASA MOD13A2.061 NDVI and MOD11A2.061 daytime LST, quality filtered from native HDF files. Seasonal NDVI/LST need ≥30%/≥20% of expected composites. VHI is 0.5×VCI + 0.5×TCI, using same-season extrema and at least 15 valid reference years. Flat ranges remain unknown. Cross-year seasons use the starting year. This is not FAO ASIS. |

The catalog reads each selected model’s `cmip6_license` attribute from an original NetCDF file and retains that attribution.

Models currently offered: ACCESS-CM2, MIROC6 and MPI-ESM1-2-HR, member r1i1p1f1. Climate baseline uses historical data through 2014 and SSP2-4.5 thereafter. Hot/warm counts use strict `>`; heavy rain uses `≥`; dry days use `<`; frost days use Tmin `< 0 °C`. Dry spells reset at New Year. Prefer 30-year periods for scientific comparisons; one-year selections are useful for software checks only.

The local toolkit's NEX **v2.0**, default future **2041–2070** and **WorldCover 2021** masks differ from the bundled Ganjam example's NEX v1.1, 2040–2069 and GLC-FCS30D 2022 masks. They must not be treated as identical inputs.

The fixed ESA WorldCover 2021 v200 mask uses cropland code 40 for vegetation health and excludes water code 80 for degradation. Its 10 m source is sampled at 50 m or coarser on an equal-area grid, then eligible area is aggregated to the analysis grid. The actual sampling scale is recorded. Full-boundary mode applies no crop/water mask and must not be described as crop-only or terrestrial-only evidence. The mask does not establish historical land use.

The toolkit prepares **five numeric modules**. Land-cover change and forest fragmentation continue to use the website's categorical GeoTIFF upload controls. After importing a numeric package, these controls use the same boundary and require matching rasters. Restore the Ganjam example to use its bundled categorical inputs.

## Data sources and accounts

- [JRC / CEMS-GloFAS flood-hazard archive](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/README.txt).
- [Trends.Earth published SDG dataset](https://doi.org/10.5281/zenodo.17514520).
- [ESA WorldCover access and attribution](https://esa-worldcover.org/en/data-access).
- [NASA NEX-GDDP-CMIP6 access and documentation](https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/).
- [NASA GLDAS 2.2 daily product](https://disc.gsfc.nasa.gov/datasets/GLDAS_CLSM025_DA1_D_2.2/summary).
- [MOD13A2.061 NDVI](https://doi.org/10.5067/MODIS/MOD13A2.061) and [MOD11A2.061 LST](https://doi.org/10.5067/MODIS/MOD11A2.061).

Groundwater and MODIS require the user's own free [NASA Earthdata account](https://urs.earthdata.nasa.gov/), with the relevant NASA application authorised. The terminal handles login through earthaccess. A new login is not persisted by this toolkit; earthaccess can use a preexisting environment or netrc login. No credentials are included in configuration, results or the website. The shared MODIS source and calculation code passed a signed-in Linux server test using 90 native HDF files for January 2009–2023 over Bhubaneswar. GLDAS requires acceptance of the NASA GESDISC DATA ARCHIVE terms. It uses up to four authenticated HTTP connections for regional daily subsets, with serial NetCDF decoding and checksum-verified caches. A signed-in Linux GLDAS test over Bhubaneswar processed 731 daily subsets (2020–2021, including leap day): 23.5 MB, four result maps, 24 monthly points, approximately 5.6 minutes. These periods test the workflow rather than establish a long-term trend. Analytical and synthetic native-file checks are also included.

## Where files and calculation live

The website creates the download ZIP in browser memory. On your computer, the extracted package stores:

| Location | Contents |
| --- | --- |
| `config.json`, `aoi.geojson` | Your selected options and checksum-linked boundary. Change options by generating a new package. |
| `.venv/` | Private Python environment and downloaded dependencies. |
| `cache/<job hash>/` | Source downloads, cropped raster windows and completed intermediate arrays. |
| `results/package/` | Prepared numeric inputs and catalog for the website. |
| `results/rasters/` | Calculated result layers, with CRS, numeric values and NoData. |
| `results/statistics.csv` | Area-weighted means, extrema, valid/eligible/missing area and coverage. Categorical distributions are also available after import through the website's Class areas CSV. |
| `results/run-manifest.json` | Configuration, source versions, methods, hashes and limitations. |
| `results/validation.json` | Actual completed modules, failures and local numeric summaries. |
| `results/README.md` | Completion status and next steps. |
| `results.zip` | Only the boundary, catalog and referenced prepared TIFFs for import. No credentials, raw data or Python environment. |

Source acquisition, QA, indices and aggregation run in local Python. NASA's existing NCSS and OPeNDAP services perform spatial subsetting when supplying climate and groundwater files; this local preparation route requires no platform backend; the optional online pyWaPOR workspace uses a separate compute service. After import, browser Web Workers read prepared rasters and calculate map differences, component combinations and area statistics. Importing does not upload files to a server. Reloading the page clears the imported session; the downloaded package and local files remain on disk.

Keep the extracted folder to resume. Starting the launcher again reuses completed files and arrays. An interrupted file request restarts that request; it does not resume at a byte offset. Cache reuse is tied to the same configuration. A newly generated package with changed settings is a separate job.

## Limits and recovery

- Boundary: WGS84 polygons between 85°S and 85°N, up to 10 MB / 100,000 coordinates / 50,000 km²; no date-line crossing. Python also checks polygon validity. Some source grids require smaller areas.
- Results: at most 100 MB per TIFF, 8 million cells per grid and 40 million input-plus-output cells per module. ZIP import allows 200 MB compressed / 350 MB unpacked and at most 40 top-level files. A catalog may describe all seven modules while marking unselected or failed ones unavailable.
- Climate downloads scale with years × models × source variables × scenarios. The wizard displays a request estimate. MODIS tiles can require tens of GB or more and hours to days. Groundwater retrieves only the regional GWS_tavg cells; long periods still need many daily requests. All streamed groundwater subset bytes count against the managed-download budget.
- The managed-download limit applies to direct requests and NASA downloads in that run. It excludes GDAL raster range requests and dependency installation, so it is not a hard total network or disk limit. Start the same package again to continue with already completed downloads; a single oversized source file needs a higher limit in a new package.
- A source failure does not become a successful diagnostic. Completed modules remain importable; others show their failure or pending state. Check connectivity, disk space, NASA authorisation, region coverage and the output README. A provider version mismatch requires review, not a silent substitution.
- If a cached file is damaged, remove the affected package's cache and rerun. Delete the extracted folder when its data and environment are no longer needed.

Protected-area/OECM applicability, causal interpretation, intervention selection and expert acceptance remain separate review tasks.

## Development validation

A rectangular **Bhubaneswar test area** (85.75–85.95°E, 20.15–20.35°N; **462.6722 km²**) verifies acquisition beyond Ganjam.

- Real public JRC RP10 + Trends.Earth/WorldCover + NEX ACCESS-CM2 historical 1991 / SSP2-4.5 2041 (hot days, temperature, heavy rain, dry spells): **37 layers and 274 browser/Python statistic checks**. These one-year climate periods validate software, not climatological conclusions.
- Downloaded the package through the local website and ran it in a newly created private Python 3.12 environment on macOS Apple Silicon. Default three flood return periods + degradation: **19 layers and 150 browser/Python checks**.
- Additional native daily-source reads: MIROC6 SSP5-8.5 precipitation 2041; MPI-ESM1-2-HR SSP2-4.5 minimum temperature 2041; ACCESS-CM2 historical minimum temperature 1991. These are retrieval/decoding checks, not full ensemble validation.
- 25 TypeScript and 27 Python unit tests pass. New tests exercise invalid settings, season calendars, missing data, VHI reference coverage, raw NetCDF/HDF reading, AOI weights, cache reuse, incomplete runs, archive paths/size/truncation, checksums and separating configuration strings from executable code.
- The Windows launcher remains unverified end to end. MODIS has a 15-year signed-in Linux server test; GLDAS has a two-full-year signed-in Linux server test. These do not validate every region, period, growing season or operating system.

Local evidence is saved under ignored `engine/outputs/localprep-bhubaneswar/` and `engine/outputs/downloaded-wizard-package/`. Recheck a prepared result with `pnpm run test:local -- <extracted-package-folder>` (or run the TypeScript script with that folder argument). These checks establish software consistency, not environmental truth.
