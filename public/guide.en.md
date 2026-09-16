# NbS Diagnostics Lab: feature guide and calculation methods

Version 0.4.0. Public-data Ganjam Step 2 screening. Expert review pending.

Choose one of the seven diagnostics. For land cover and forest, keep Ganjam 2002/2012/2022, 50 m cells and 50 m edge width, then run. Other modules use prepared numeric inputs; select a layer after running and inspect its coverage.

## How does it compute without an analysis backend?

GitHub Pages serves static HTML, CSS, JavaScript and public sample files. Your browser executes the downloaded program using your computer's CPU and memory. The main thread manages controls, maps and downloads; a separate Web Worker reads rasters, aligns and reclassifies them, and calculates change and fragmentation before returning arrays. A Web Worker is a browser thread, not a remote server. Uploaded file contents are not sent to a server. Basemap tiles and sample downloads still need the network. Earth Engine and Python prepare public source data before publication. The five numeric modules read prepared values and area weights, then perform map arithmetic, subindicator combination and statistics locally. Upstream satellite composites, climate projections and provider models are not rerun inside the page.

Current caps: 100 MB and 25 million input pixels per TIFF, 8 million analysis cells, 25 MB per vector file, and 3 periods. Usable size also depends on device memory. Crop or coarsen larger jobs, or use the repository's separate Python command-line engine; the website does not call that engine.

## 1. Study-area overview

**How to use:** Use Locate study area to fit the boundary and Regional context to see its surroundings. Overview in the header returns here.

**How it works:** The demo reads the Ganjam GeoJSON. Uploads show the AOI, or the earliest-year GeoTIFF footprint transformed to longitude/latitude. MapLibre draws the outline and fits the view over OpenStreetMap tiles. The selected result is overlaid on this shared map. Use the year selector for land cover and forest, and the layer selector below for numeric diagnostics. Opacity and visibility affect only display.

## 2. Public example and years

**How to use:** Choose Public data, keep 2002, 2012, 2022 and 50 m, then run both modules. Download the sample TIFFs to try the upload workflow.

**How it works:** GLC-FCS30D is a consistent 30 m product. Earth Engine and Python prepare the cropped 50 m EPSG:6933 inputs with nearest-neighbour sampling. The browser verifies hashes and applies an editable ten-class crosswalk. The source fine classes remain in the input files. Classification errors and resampling mean mapped change still needs local review.

## 3. Upload rasters, AOI and class inspection

**How to use:** Choose Upload your own GeoTIFFs, enter years and select 1–3 single-band categorical TIFFs. Load raster class codes lists their categories. Optionally add an AOI GeoJSON or one zipped Shapefile; otherwise analysis uses the earliest-year raster extent.

**How it works:** geotiff.js reads pixels and georeferencing; proj4 transforms WGS84, WGS84 UTM, Web Mercator and EPSG:6933. GeoJSON must use WGS84; a Shapefile ZIP needs .shp, .dbf and .prj. Code 0 and declared NoData are excluded. Convert RGB images, rotated grids and PixelIsPoint rasters in GIS first.

## 4. Diagnostic module

**How to use:** LULC change needs 2–3 distinct years. Forest fragmentation accepts 1–3 years. Running both needs 2–3.

**How it works:** LULC compares adjacent periods plus first-to-last when three years are supplied: three periods yield three comparisons. Fragmentation is calculated independently for each year.

## 5. Analysis resolution

**How to use:** Grid resolution is in metres. Start at 50 m; use 100 m or coarser for larger areas. Edge width must be at least one analysis cell.

**How it works:** Inputs are aligned by nearest-neighbour sampling to one EPSG:6933 equal-area grid; pixel centres determine AOI membership. Area in hectares = pixel count × cell size² / 10,000. Finer grids need more memory; upsampling the 50 m public inputs does not restore 30 m source detail.

## 6. Reclassification crosswalk

**How to use:** Expand Reclassify land cover. Source is the original code; Target, Name and Colour define the unified class. Merge sources by giving them the same target code, name and colour, or import a CSV.

**How it works:** After alignment, each pixel is recoded with one shared crosswalk for all years. Every observed source must be mapped. CSV columns: source_code,target_code,target_name,color. Target codes are 1–999; colours use #RRGGBB. Colours alone do not alter area; merging classes changes the analysis.

## 7. Forest definition

**How to use:** Select target classes in Classes counted as forest. The GLC-FCS30D project legend defaults to Forest including mangroves (2); orchards remain cropland. Review your selection after reclassification.

**How it works:** Selected classes become a binary forest mask; other valid classes are non-forest. This is a user-defined analytical mask. Tree cover is not automatically a national legal definition of forest.

## 8. Edge width and boundary option

**How to use:** Set Forest edge width, for example 50 or 100 m. Count AOI / NoData boundaries as edges is off by default; enable it to count study-area and missing-data boundaries.

**How it works:** An exact Euclidean distance transform measures pixel-centre distance to the nearest non-forest pixel. Distance strictly greater than the threshold defines candidate core; the remainder is candidate edge. Counting unknown boundaries reduces core near them. Protection boundaries never create forest edges.

## 9. Protected areas and OECM

**How to use:** Expand Protection & OECM layers and upload either or both polygon datasets. Run a fragmentation module. Use complete coverage for your study area.

**How it works:** Classify the whole landscape first, then summarise Protected, OECM and remainder, with Protected taking precedence. Area is allocated by pixel. NP, MPS, MPE, MSI and AWMSI assign each whole patch to its majority stratum; ties prefer Protected, OECM, then remainder. LPI uses actual intersection area. Remainder only means outside supplied polygons, not legally unprotected.

## 10. Land-cover and class-difference maps

**How to use:** After a run, choose Land cover for yearly maps or Class difference for pairwise differences, including first-to-last. Hover to inspect pixel classes and use the legend for colours.

**How it works:** Canvas colours the calculated arrays with transparent NoData. Differences use only cells valid in both periods: same class = 0, different = 1. The overview basemap does not enter area or distance calculations.

## 11. Transition matrix, gains and losses

**How to use:** Choose the comparison period. Rows are earlier classes, columns are later classes, and values are hectares. Diagonal cells retain their class; off-diagonal cells are transitions.

**How it works:** Count from→to pairs within common valid coverage. Gross loss is the off-diagonal row sum; gross gain is the off-diagonal column sum; net = gain − loss. Yearly area tables use each year's own coverage, so their area difference may differ from net change when valid footprints differ.

## 12. Forest-fragmentation map

**How to use:** Choose Forest fragmentation: green Core, yellow Edge, red Patch (a forest patch without core), purple Internal clearing, neutral Non-forest, and transparent NoData.

**How it works:** Forest components use 8-neighbour connectivity, including diagonals. A component without any core cell becomes Patch; others retain Core and Edge. Non-forest uses 4-neighbour connectivity; components touching the exterior or NoData are not clearings. Core + Edge + Patch equals total forest area; clearings are excluded.

## 13. Forest metrics

**How to use:** Compare years and strata in Fragmentation by year & protection. Interpret patch counts with core area, resolution and the forest definition; NP alone does not measure ecological quality.

**How it works:** Metrics use connected-component areas and raster-side perimeters. NP counts all connected forest patches, not only the red Patch class. Formulas are below. Raster shape metrics depend on the boundary option; this reference adaptation is not guaranteed to match ArcPy polygon perimeter measurements exactly.

## 14. Run, stop and export

**How to use:** Use Run with current settings or Run analysis. Pan the map while computing; Stop computation / Cancel analysis ends the run. Results appear below the overview. Changed settings require another run.

**How it works:** GeoTIFF preserves the full grid, CRS and NoData. PNG includes the display legend. CSV exports areas, transitions, gains/losses and forest metrics. Run manifest JSON records hashes, settings, crosswalk, checks and limitations. Downloads are generated locally. Stopping terminates the Worker; closing or refreshing loses in-memory results.

## Forest metric definitions

| Field | Meaning | Formula / convention |
| --- | --- | --- |
| landscape_ha | Valid landscape area | Valid cells × cell area (ha) |
| forest_ha / PLAND | Forest area / cover | PLAND = forest_ha / landscape_ha × 100% |
| core_ha / edge_ha / patch_ha | Core / edge / patch area | The three areas sum to forest_ha |
| clearing_ha | Internal clearing area (non-forest) | Excluded from forest_ha |
| core_pct | Core share of forest | core_ha / forest_ha × 100% |
| NP | Connected forest patch count | All forest components, using 8-neighbour connectivity |
| TE_m / ED | Total edge / edge density | ED = TE_m / landscape_ha (m/ha) |
| MPS_ha / MPE | Mean patch area / mean perimeter | Sum of whole-patch area (ha) or perimeter (m) / NP |
| MSI / AWMSI | Mean / area-weighted shape index | Per-patch shape = 0.25 × perimeter(m) / √area(m²); MSI = mean(shape); AWMSI = Σ(shape × area) / Σarea |
| LPI / largest_patch_ha | Largest patch index / area | LPI = largest_patch_ha / landscape_ha × 100%; use actual within-stratum intersection area |
| clearings_intersecting | Clearings intersecting the stratum | A clearing may intersect multiple strata; do not add stratum counts |

## River flood hazard

Which areas intersect modelled river flooding?

Run the diagnostic, choose a map layer, inspect coverage and source resolution, then download GeoTIFF, PNG, CSV and the manifest. Prepared time series have a selector and CSV export.

- Read JRC/CEMS-GloFAS water depths for multiple return periods on the native 3-arc-second grid.
- Retain permanent-water and spurious-depth flags. Report mapped inundation extent and depth, with unknown coverage explicit.
- Official JRC v2.1.2 depth and flag tiles. Nearest-neighbour alignment to a common 3-arc-second WGS84 grid; no spatial downscaling. Positive mapped depths only; permanent water and provider-flagged spurious depths excluded. Dry / unmodelled NoData remains unknown. AOI intersections weighted in EPSG:6933.
- Depth distributions use mapped valid inundation as their denominator. Coverage uses the entire district AOI. Both areas are exported.

Limitations:

- Riverine hazard does not cover coastal storm surge, all small catchments or urban drainage.
- Return periods describe probabilities under model assumptions; they are not dates of future floods.
- NoData in the raw depth product does not distinguish dry cells from unmodelled areas. It is not replaced with zero.

Step 3 field checks:

- Do documented flood extents match the mapped river corridors?
- Where do embankments, drainage failures or storm surge change local exposure?

## Groundwater storage

How has regional groundwater storage changed?

Run the diagnostic, choose a map layer, inspect coverage and source resolution, then download GeoTIFF, PNG, CSV and the manifest. Prepared time series have a selector and CSV export.

- GLDAS 2.2 GWS_tavg. Monthly means require at least 90% daily coverage; period means require at least 90% monthly coverage. February 2003–December 2013 baseline; January 2014–December 2023 monitoring. Equal-month weighting. Native grid retained; fractional AOI intersections in EPSG:6933. Annual trend is Theil-Sen, requiring at least 19 valid years; no significance claim.
- Browser differences and summaries use the common valid footprint and AOI area weights.

Limitations:

- Modelled water storage in millimetres is not measured groundwater-table depth.
- The coarse regional signal cannot locate a failing well or resolve villages.
- January 2003 is absent from the provider collection and has not been imputed.
- A storage trend can reflect climate and the model's assumptions; it does not isolate pumping or recharge mechanisms.

Step 3 field checks:

- Do local well hydrographs corroborate the seasonal pattern and long-term change?
- Have pumping, irrigation or recharge practices changed?

## Climate extremes

How could heat, rainfall extremes and dry spells change?

Run the diagnostic, choose a map layer, inspect coverage and source resolution, then download GeoTIFF, PNG, CSV and the manifest. Prepared time series have a selector and CSV export.

- NASA NEX-GDDP-CMIP6 version 1.1; ACCESS-CM2, MIROC6 and MPI-ESM1-2-HR. Historical 1991–2014 + SSP2-4.5 2015–2020 form the baseline; compare SSP2-4.5 and SSP5-8.5 for 2040–2069.
- Daily Kelvin temperatures converted to Celsius; precipitation kg m⁻² s⁻¹ multiplied by 86,400 to mm/day. Hot days Tmax>35°C, warm nights Tmin>20°C, frost days Tmin<0°C, heavy rain>100 mm/day, and daily mean temperature.
- Dry spells use precipitation <1 mm/day. Annual mean spell length = dry days / runs of dry days; a dry spell crossing 1 January is split at the year boundary. A year with no dry days has length zero.
- Annual indices require every calendar day valid. Compute each model’s 30-year mean, then the equal-weight three-model mean. Minimum/maximum changes are taken across individual model changes. Preserve leap-year day counts.
- Keep the 0.25° grid and weight district statistics by exact AOI-cell intersections. The individual-model climatologies remain in the source package; annual ensemble series are exported separately.

Limitations:

- SSP2-4.5 and SSP5-8.5 are available public-data scenarios, not the original report’s RCP2.6. A low-emission scenario is deferred; do not interpret these outputs as RCP2.6 results.
- Three models are a limited ensemble. Their range is not a confidence interval and does not represent the full CMIP6 uncertainty distribution. Downscaling does not resolve village microclimates.
- Baseline is modelled, not station observation. The 2015–2020 historical extension follows SSP2-4.5. Thresholds need local impact review. No combined risk score or arbitrary weighting is applied.
- The series has an intentional gap between 2020 and 2040. Future annual points are model projections, not event forecasts.

Step 3 field checks:

- Which heat, rainfall and dry-spell thresholds matter for local crops, health and infrastructure?
- Do weather-station records reveal local model biases?
- How do planning decisions change between the two scenarios and across model spread?

## Land degradation

Where do productivity, land-cover and soil-carbon indicators deteriorate?

Run the diagnostic, choose a map layer, inspect coverage and source resolution, then download GeoTIFF, PNG, CSV and the manifest. Prepared time series have a selector and CSV export.

- Use the published Trends.Earth SDG 15.3.1 v1.2 product; preserve its productivity, land-cover and SOC subindicators and its native ~250 m geographic grid.
- Baseline: SDG 2000–2015 with productivity 2001–2015. Latest assessment: productivity 2008–2023, land-cover/SOC changes 2015–2022 as documented in the dataset record.
- LPD 1/2 → degraded, 3/4 → stable, 5 → improving. SOC <−10% → degraded, >10% → improving; exactly ±10% in the integer product is treated as uncertain because upstream rounding can cross the threshold. Apply one-out-all-out to the three classified subindicators in the browser.
- Compare the local result with the published combined indicator on complete jointly observed cells. Retain a separate three-component completeness map and the published seven-class 2023 status.
- Eligible area = AOI intersection minus estimated 2022 open-water fraction from GLC-FCS30D, averaged onto the source grid. This fixed terrestrial denominator is independent of product missingness; small boundary/mixed-pixel differences from national reporting are expected.

Limitations:

- The three upstream subindicators are published model outputs. The browser recalculates their combination and area statistics; it does not rerun the publisher’s global NDVI or SOC model.
- Four baseline cells differed from the provider when rounded SOC=-10% was classified as degraded. Values exactly ±10% are now marked uncertain, retaining the original percentage and publisher result for inspection.
- SOC is modelled from land-cover change with stock-change factors; it is not measured soil-carbon loss. Local management, climate and soil samples need validation.
- The dataset record labels latest land-cover/SOC bands 2015–2022, whereas embedded TIFF descriptions say 2015–2023. The UI follows the published record and retains both labels in provenance. Confirm this discrepancy before formal reporting.
- A known negative component is retained as a conservative degradation flag even if another is missing. Such pixels are distinguishable using component completeness and are excluded from the publisher-agreement test.
- Fixed 2022 open-water exclusion and source differences mean percentages are a Ganjam screening estimate, not official national SDG statistics.

Step 3 field checks:

- Which mapped declines coincide with soil erosion, loss of cover, crop changes or restoration histories?
- Can soil sampling and management histories corroborate the modelled SOC change?
- Are the provider’s transition rules and water exclusions appropriate for Ganjam?

## Drought & vegetation stress

How did seasonal vegetation health change on mapped cropland?

Run the diagnostic, choose a map layer, inspect coverage and source resolution, then download GeoTIFF, PNG, CSV and the manifest. Prepared time series have a selector and CSV export.

- Kharif = June–October; Rabi = November–March of the following year. Calendar assumptions require local review.
- NDVI SummaryQA≤1 (good or marginal); LST mandatory QC bits=0 and LST error bits <=1 (<=2 K). Each season requires >=30% of NDVI composites and >=20% of LST composites valid. Observation percentages are separate map outputs.
- VCI=100*(NDVI-min)/(max-min); TCI=100*(max-LST)/(max-min); VHI=0.5*VCI+0.5*TCI. Same-season 2001–2023 climatology, >=15 valid years per variable; zero ranges are NoData.
- Fixed 2022 cropland codes 10/11/12/20, including orchards. Crop area is aggregated from 50 m equal-area pixels with fractional AOI intersections. Climate pixels retain their 1 km scale.
- Two-season annual summary requires both seasons and gives equal weight to each. No FAO crop-stage coefficients are applied.

Limitations:

- This is a MODIS seasonal screening alternative, not FAO ASIS or its crop-stage-weighted VHI. The ASIS asset was unavailable to the registered project.
- Min/max VHI is sensitive to reference years and outliers. Seasonal means do not reproduce a dekadal agricultural drought product. At least 15 of 23 seasonal years per variable must support the reference range. Clear-sky sampling can bias the monsoon signal; inspect missing area and each time-series coverage value.
- Vegetation and thermal stress can arise from crop choice, fallow land, pests or management. The fixed 2022 cropland mask does not establish historical cropping or irrigation.

Step 3 field checks:

- Are June–October and November–March appropriate for the local crops and planting dates?
- Do low-VHI years correspond to farmer reports, rainfall deficits or irrigation interruptions?

## Required outputs and acceptance

Each module exposes maps, numeric exports, statistics, provenance and field-check questions. Download the diagnostic brief to collect the evidence available in the current session. Refreshing the page clears in-memory runs; export before closing.

A complete protected-area / OECM overlay and applicability review have not been supplied. No absence is inferred.

Technical screening for expert review. Completion requires review of all seven modules, protection applicability, uncertainties and field-check questions.

The first release defers automated arbitrary-AOI data ingestion, RCP2.6 / a low-emission climate scenario, authenticated ASIS access, event forecasting, unified risk scores, additional hazard modules, intervention selection and cost-benefit analysis.

## Sources

- [JRC / CEMS-GloFAS global river flood hazard](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/README.txt) — 2.1.2 · 2026-01-12; Free and open Copernicus product; attribution required.
- [NASA GLDAS 2.2 Catchment / GRACE data assimilation](https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V022_CLSM_G025_DA1D) — V022 / CLSM / G025 / DA1D; NASA Earth Science open data.
- [GLC-FCS30D annual land cover](https://essd.copernicus.org/articles/16/1353/2024/) — 1985–2022 release; annual bands 2002, 2012, 2022; CC BY 4.0.
- [NASA NEX-GDDP-CMIP6](https://developers.google.com/earth-engine/datasets/catalog/NASA_GDDP-CMIP6) — Earth Engine collection version 1.1 (verified image-property histogram); prepared September 2026; CMIP6 terms; CC BY 4.0 for ACCESS-CM2, MIROC6 and MPI-ESM1-2-HR via NEX-GDDP-CMIP6.
- [Trends.Earth SDG 15.3.1 public data](https://zenodo.org/records/17514520) — 1.2, published 3 November 2025; Trends.Earth LPD variant; CC BY 4.0.
- [NASA MODIS seasonal NDVI and land-surface temperature](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A2) — MOD13A2.061 + MOD11A2.061; crop-start years 2001–2023; NASA LP DAAC: unrestricted use and redistribution.
