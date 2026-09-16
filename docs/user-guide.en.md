# NbS Diagnostics Lab — User Manual

**Ganjam Step 2 · Version 0.4.0 · 16 September 2026**

[Open the public website](https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/) · [GitHub repository](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab) · [Download this manual](https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/guide.en.md)

This manual explains how to use all seven diagnostics, which public datasets were used for the Ganjam tests, how calculations work, and what the results can support. The first release provides public-data screening for technical review. A successful calculation is not expert acceptance or field validation.

## Contents

1. [Start a diagnostic](#1-start-a-diagnostic)
2. [Understand the map and result controls](#2-understand-the-map-and-result-controls)
3. [Data used for testing](#3-data-used-for-testing)
4. [Where calculations happen](#4-where-calculations-happen)
5. [Seven modules: operation and calculation](#5-seven-modules-operation-and-calculation)
6. [Area, coverage and missing data](#6-area-coverage-and-missing-data)
7. [Export and assemble the review package](#7-export-and-assemble-the-review-package)
8. [Use your own inputs](#8-use-your-own-inputs)
9. [Validation and reproducibility](#9-validation-and-reproducibility)
10. [Troubleshooting](#10-troubleshooting)
11. [Completion standard and deferred work](#11-completion-standard-and-deferred-work)

## 1. Start a diagnostic

Use a recent desktop browser with JavaScript and WebGL enabled. No Google account, Earth Engine login or software installation is required to run the published example. Initial code, data and basemap downloads need an internet connection. Large custom inputs depend on available device memory.

1. Open the website. Check that the overview identifies **Ganjam District, Odisha** and the boundary is ready. Select **Locate study area** if necessary.
2. Select **Land-cover change**. Keep **Public data**, the years **2002, 2012, 2022**, **50 m** grid resolution and **50 m** forest edge width. Choose both land-cover and fragmentation analysis if you want both outputs from one run.
3. Select **Run with current settings** or **Run analysis**, depending on the expanded input view. Wait for completion. Review the three comparisons: **2002–2012**, **2012–2022** and **2002–2022**.
4. Select **Forest fragmentation** to inspect the forest results from that run. Changing the crosswalk, forest definition, resolution or edge width requires a new run.
5. Select **Groundwater storage**, **Drought & vegetation**, **Climate extremes**, **River flood hazard** or **Land degradation**. Select **Run diagnostic**, then choose an output in **Map layer**. These modules use the prepared data described below; their source periods and thresholds are not changed by the land-cover form.
6. Read **Valid coverage**, **Source resolution**, **Calculation method & limitations** and **Questions for Step 3 field checks**. Select a time series where available.
7. Export the results you need. After running all modules, select **View completion checklist** and **Download diagnostic brief** in **Step 2 review package**.

Results remain in memory while switching modules. Refreshing or closing the page clears the session; download outputs first. The **7 / 7** indicator means seven modules have prepared inputs. The checklist separately records which modules have actually run in the current session.

## 2. Understand the map and result controls

| Control | What it does |
| --- | --- |
| Overview | Scrolls back to the shared study-area map. |
| Locate study area | Fits the selected boundary or input raster extent. |
| Regional context | Zooms out to show surrounding geography. |
| Result layer | Shows or hides the calculated overlay. |
| Layer opacity | Adjusts visibility without changing numeric values. |
| Overview map year | Selects a land-cover/forest year after a categorical run. |
| Map layer | Selects a numeric diagnostic output and updates its map and statistics. |
| Time series | Selects a prepared district series; missing periods remain gaps. |
| Cancel / Stop computation | Terminates the active browser worker. |

The overview stays mounted when analyses run or modules change. Results appear in the same page. Use **Overview** after reading lower tables; the map is not a fixed panel that remains on screen at every scroll position. A custom land-cover AOI and the prepared Ganjam numeric modules can have different extents, so always check the displayed study-area label.

The OpenStreetMap basemap provides context. It is not used to calculate land-cover area, forest distance or hazard values. Zooming in, smoothing the display or changing opacity does not improve source resolution.

## 3. Data used for testing

The supplied diagnostics use **real public satellite and model data cropped to Ganjam District, Odisha, India**. They are not randomly generated demonstrations. The bundled geoBoundaries gbOpen IND ADM2 boundary is labelled 2021; its calculated area is approximately **8,407.09 km²**. This is the area of the supplied geometry, not a claim about the official administrative area.

| Diagnostic / purpose | Public source and access | Periods used in this release | Source scale and prepared grid |
| --- | --- | --- | --- |
| LULC and forest | [GLC-FCS30D, Zhang et al. (2024)](https://essd.copernicus.org/articles/16/1353/2024/); [dataset DOI](https://doi.org/10.5281/zenodo.8239305). Community Earth Engine asset `projects/sat-io/open-datasets/GLC-FCS30D/annual`; four tiles E80N20, E80N25, E85N20, E85N25. | 2002, 2012, 2022, from the 1985–2022 release | 30 m source; nearest-neighbour preparation at 50 m in EPSG:6933. |
| Groundwater storage | [NASA GLDAS 2.2 Catchment / GRACE-DA](https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V022_CLSM_G025_DA1D), `NASA/GLDAS/V022/CLSM/G025/DA1D`, band `GWS_tavg`. | February 2003–December 2023; 251 monthly values | Native 0.25° grid; storage in mm. |
| Drought / vegetation stress | NASA [MOD13A2.061 NDVI](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A2) and [MOD11A2.061 daytime LST](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A2); GLC-FCS30D 2022 cropland mask. | Same-season reference 2001–2023; 2013 versus 2023 maps; Rabi extends into the next calendar year | 1 km NDVI/LST; 16-day / 8-day composites. Fine crop area is aggregated into the 1 km grid. |
| Climate extremes | [NASA NEX-GDDP-CMIP6](https://developers.google.com/earth-engine/datasets/catalog/NASA_GDDP-CMIP6), Earth Engine image version 1.1; ACCESS-CM2, MIROC6, MPI-ESM1-2-HR. | Baseline 1991–2020; future 2040–2069 under SSP2-4.5 and SSP5-8.5 | Native 0.25° daily projections; no additional spatial downscaling. |
| River flooding | [JRC / CEMS-GloFAS global flood hazard](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/README.txt), v2.1.2 dated 12 January 2026; tiles ID192_N30_E80 and ID193_N20_E80. | 10-, 100- and 500-year return-period scenarios, not observation years | Native 3 arc seconds, approximately 90 m; modelled depth in metres. |
| Land degradation | [Trends.Earth SDG 15.3.1 v1.2](https://zenodo.org/records/17514520), DOI 10.5281/zenodo.17514520; Trends.Earth LPD variant of the published global COG. | Baseline SDG 2000–2015, productivity 2001–2015; latest productivity 2008–2023, land-cover/SOC changes 2015–2022 in the dataset record | Approximately 250 m geographic grid; published productivity, land-cover and modelled soil-carbon subindicators. |
| Boundary and basemap | [geoBoundaries gbOpen](https://www.geoboundaries.org/) IND ADM2, Ganjam; [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). | Bundled boundary labelled 2021; live contextual basemap | Boundary is the analysis extent; basemap tiles are display only. |
| Retained regression example | [ESA WorldCover](https://esa-worldcover.org/en/data-access) 2020 v100 and 2021 v200 in `public/data/worldcover`. | 2020 and 2021 | 10 m source, 50 m prepared grid. Used by automated regression checks; not the default diagnostic series. |

The WorldCover releases use different algorithms, so their changes should not be treated as a consistent environmental time series. The MODIS drought package is an explicit alternative to inaccessible FAO ASIS; it is not ASIS output. The climate package does not implement the reference report's RCP2.6 scenario.

**Attribution:** GLC-FCS30D, the selected NEX models and Trends.Earth are recorded under CC BY 4.0; NASA GLDAS/MODIS use their respective open-data terms; JRC/Copernicus attribution applies to flood data; geoBoundaries is recorded under ODbL 1.0. Preserve original source attribution when sharing derivatives. Exact versions, source URLs, licences, preparation rules, raster bands and SHA-256 hashes are in the [data catalog](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/public/data/step2/catalog.json) and [GLC-FCS30D metadata](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/public/data/glcfcs/metadata.json).

## 4. Where calculations happen

| Stage | Location | Work performed |
| --- | --- | --- |
| Source preparation | Earth Engine and local Python, before publication | Acquire public sources, apply quality masks, aggregate dates, compute VHI/climate indices/trends, crop rasters and calculate AOI-intersection weights. |
| Distribution | GitHub Pages | Serve HTML, CSS, JavaScript, prepared public GeoTIFFs and metadata over HTTPS. |
| Interactive analysis | Web Workers in the visitor's browser | Verify hashes; align/reclassify categorical inputs; calculate transitions and fragmentation; calculate numeric differences, land-degradation combinations and area-weighted statistics. |
| Presentation and export | Browser main thread | Keep the shared map, display tables/series, render images and create download files. |

A Web Worker is a computation thread on your device. It is not a remote analysis server. The website does not rerun global climate models, authenticate to Google, launch Earth Engine tasks or call the repository's Python engine. It can calculate without a custom backend because the program and prepared inputs are downloaded to your browser.

Uploaded file contents are processed locally by the application. Public data and basemap requests still use the network. No Google credentials or service-account keys are shipped with the website. Preparing fresh source data requires separate authorized access and is documented in the [data workflow](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/docs/step2-data.md).

## 5. Seven modules: operation and calculation

### 5.1 Land-cover change

**Use:** Select the public example, inspect **Reclassify land cover**, run the analysis, then inspect yearly maps, **Class difference**, the transition matrix and gain/loss tables. Select each of the three comparison periods.

Fine source codes are retained in the input TIFFs and mapped at runtime to ten editable target classes: cropland, forest, shrubland, grassland, wetland, built-up, bare land, water, snow/ice, and other/sparse cover. The default forest class includes mangroves; orchards remain cropland. The [crosswalk CSV](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/public/data/glcfcs/crosswalk.csv) records every source-to-target mapping.

Inputs are aligned by nearest-neighbour sampling to an equal-area EPSG:6933 grid. Pixel centres determine membership in the AOI. For cell size `r` metres, class area in hectares is `class pixel count × r² / 10,000`. At 50 m, one full cell represents 0.25 ha.

For each pair, use only cells valid in both years. Transition `i → j` is the count of those class pairs multiplied by cell area. Matrix rows are earlier classes; columns are later classes. Gross loss is the off-diagonal row sum, gross gain is the off-diagonal column sum, and net change is gain minus loss. Difference maps code unchanged as 0 and changed as 1; NoData stays missing.

Yearly totals use each year's own valid footprint. Their difference can therefore differ from common-footprint net change. Classification errors and 50 m resampling can affect small patches; mapped change requires interpretation.

### 5.2 Forest fragmentation

**Use:** Choose **Classes counted as forest**, **Forest edge width** and the **Count AOI / NoData boundaries as edges** option. Run, select **Forest fragmentation**, compare years, and inspect the metrics. Default settings are forest target class 2, 50 m cells, 50 m edge width, and unknown-boundary counting off.

1. Reclassify selected target classes to a binary forest mask.
2. Calculate exact Euclidean pixel-centre distance to non-forest. Forest farther than the edge width is candidate core; the remaining forest is candidate edge.
3. Label forest components with **8-neighbour connectivity**, including diagonals. A component with no core becomes **Patch**; components with core retain **Core** and **Edge**.
4. Label non-forest with **4-neighbour connectivity**. A component enclosed by forest and not touching the exterior or NoData becomes **Internal clearing**. It remains non-forest and is excluded from total forest area.

Core + Edge + Patch equals total forest. NP counts every connected forest component, not only the map's red Patch category. Distances and perimeters depend on resolution and the boundary option. The implementation follows the supplied ArcPy reference's analytical ideas but uses raster distances/perimeters; it does not promise identical polygon perimeter results.

| Metric | Calculation |
| --- | --- |
| PLAND | Forest area / valid landscape area × 100%. |
| Core share | Core area / forest area × 100%. |
| NP | Number of connected forest components. |
| TE / ED | Total forest edge length in metres; ED = TE / landscape area in ha. |
| MPS / MPE | Sum of patch areas in ha / NP; sum of patch perimeters in metres / NP. |
| MSI | Mean of `0.25 × perimeter(m) / sqrt(area(m²))` across patches. |
| AWMSI | Area-weighted mean of the same patch shape index. |
| LPI | Largest patch area / valid landscape area × 100%. |

**Optional protection/OECM layers:** Upload complete polygon datasets in **Protection & OECM layers**. Classification happens before stratification, so protection boundaries do not create forest edges. Protected takes precedence over OECM, followed by the remainder. Whole-patch metrics use majority-area assignment; ties follow that order. LPI uses actual within-stratum intersection area. Remainder means outside supplied polygons, not legally unprotected. No complete protection dataset or applicability review is bundled.

### 5.3 Groundwater storage

**Use:** Run the diagnostic. Select baseline storage, monitoring storage, change or annual trend in **Map layer**. Inspect the monthly series and its coverage; export it with **Time series CSV**.

Preparation forms monthly means of daily GLDAS `GWS_tavg`, requiring at least 90% daily availability. Period means require at least 90% available months and weight months equally. Baseline is **February 2003–December 2013**; monitoring is **January 2014–December 2023**. January 2003 is not imputed. The browser subtracts baseline from monitoring on their common valid footprint.

Annual trend is the median of pairwise slopes, `median((value[j] − value[i]) / (year[j] − year[i]))`, applied to annual means and requiring at least 19 valid years of 2003–2023. The 2003 annual value covers February–December. The trend is in mm/year; no significance or causal attribution is claimed.

Storage in mm is water-equivalent regional storage, not measured water-table depth. The 0.25° grid cannot locate a failing well. As a reproducibility check, this package's district baseline and monitoring means are approximately **584.72959 mm** and **589.18674 mm**, each covering approximately **8,052.644 km²**. These values describe this dataset and mask.

### 5.4 Drought and vegetation stress

**Use:** Run, compare Kharif/Rabi VHI for 2013 and 2023, inspect change layers and observation-coverage layers, then select the seasonal time series. Rabi 2013 means November 2013–March 2014; Rabi 2023 extends through March 2024.

Preparation uses **Kharif June–October** and **Rabi November–March**, with a same-season 2001–2023 reference. Quality rules retain NDVI SummaryQA ≤1, good mandatory LST QA and reported LST error ≤2 K. Each season needs at least 30% valid NDVI composites and 20% valid LST composites. Each pixel needs at least 15 valid reference years per variable and a nonzero reference range.

```text
VCI = 100 × (NDVI − reference minimum NDVI) / (reference maximum NDVI − reference minimum NDVI)
TCI = 100 × (reference maximum LST − LST) / (reference maximum LST − reference minimum LST)
VHI = 0.5 × VCI + 0.5 × TCI
```

Lower VHI indicates poorer relative vegetation/thermal condition. Display bands are `<10`, `10–<20`, `20–<30`, `30–<40` and `≥40`; these do not establish crop losses. The annual summary needs both seasons and weights them equally. Changes use only jointly valid observations.

A fixed GLC-FCS30D 2022 cropland mask, including orchards, supplies eligible crop area. Fine 50 m AOI-intersection areas are aggregated into the 1 km cells. NDVI/LST keep their 1 km information scale.

**This is not FAO ASIS.** It does not apply ASIS crop-stage coefficients. The lower LST availability threshold allows a usable monsoon reference but leaves clear-sky sampling bias; inspect coverage alongside every result. Crop calendars, irrigation, fallow land and management require local review.

### 5.5 Climate extremes

**Use:** Run, then choose the indicator, period/scenario and change or model-range layer in **Map layer**. Select the matching annual series. The 2020–2040 gap is intentional; future points are projections, not forecasts of individual events.

Preparation uses three models with equal weight. Baseline combines historical **1991–2014** with **SSP2-4.5 for 2015–2020**. Future climatologies cover **2040–2069** under SSP2-4.5 and SSP5-8.5. Kelvin is converted to Celsius; precipitation in kg m⁻² s⁻¹ is multiplied by 86,400 to obtain mm/day.

| Annual index | Definition used here |
| --- | --- |
| Hot days | Count of days with Tmax >35°C. |
| Warm nights | Count of days with Tmin >20°C. |
| Frost days | Count of days with Tmin <0°C. |
| Mean temperature | Annual average of daily `tas`, in °C. |
| Heavy-rain days | Count of days with precipitation >100 mm/day. |
| Mean dry-spell length | Dry days / number of dry runs, where precipitation <1 mm/day. A run crossing 1 January is split; a year with no dry days has length zero. This is not maximum consecutive dry days. |

Every calendar day must be valid for an annual index. Calculate each model's 30-year average, then the three-model mean. Future-minus-baseline maps are computed in the browser. Minimum/maximum change layers use individual model changes. Leap years retain their actual day counts.

The 54 layers include baseline, future, change and model-range outputs; they are not 54 independent hazards. The three-model range is not a confidence interval. Baseline values are modelled rather than observed station data. SSP2-4.5/SSP5-8.5 are not RCP2.6; a low-emission scenario remains deferred.

### 5.6 River flood hazard

**Use:** Run and inspect **10-year**, **100-year** and **500-year** depth layers. Check permanent-water and spurious-depth flags separately. Review inundated area and depth distribution for each return period.

Preparation reads the public JRC COG tiles, aligns them by nearest neighbour on a common native 3-arc-second grid, and retains positive depths after excluding permanent water and provider-flagged spurious depths. The browser calculates AOI-weighted inundated area and mean depth on valid mapped inundation. Depth bands are 0–<1 m, 1–<3 m, 3–<10 m and ≥10 m. The display colour ramp may saturate at 5 m; GeoTIFF values retain the full depth range.

A T-year return period corresponds to an annual exceedance probability of approximately 1/T under the model assumptions; it is not a schedule. These are riverine hazards, not coastal storm surge or a complete representation of urban drainage and small catchments. Blank depth cells cannot establish safe or dry land: source NoData can also mean unmodelled area. Depth coverage percentages therefore describe mapped inundation relative to the district, not overall model quality.

### 5.7 Land degradation

**Use:** Run, inspect the combined baseline/latest screening layers, and then inspect productivity, land-cover change, SOC percentage change and the **component completeness** layer. Compare the published indicator and seven-class status layer. Use class-area summaries rather than treating class codes as continuous measurements.

The input retains all three published subindicators. It does not infer SOC change from a single static soil map. Preparation maps productivity LPD classes 1/2 to degraded, 3/4 to stable, and 5 to improving. Published land-cover subindicator classes are retained. Modelled SOC change below −10% is degraded and above +10% is improving. Values strictly between these thresholds are stable; integer values exactly ±10% are uncertain because source rounding may cross a threshold.

The browser combines classes by **one-out-all-out**:

1. Any known degraded component flags degradation, even when another component is missing.
2. Otherwise all three components must be present: any improving component means improving; all stable means stable.
3. Without a known degraded component and without all three components, the combined result is NoData.

Partially observed degradation flags are distinguished by component completeness and excluded from the provider-agreement check. The eligible denominator is a fixed terrestrial AOI area after estimated 2022 open-water exclusion, rather than only observed product pixels.

The latest productivity period is 2008–2023. The dataset record lists latest land-cover/SOC change as 2015–2022, but TIFF band descriptions say 2015–2023. This discrepancy is preserved in provenance and requires confirmation before formal reporting. SOC is modelled using land-cover stock-change factors, not measured soil-carbon loss. Outputs are screening estimates, not official SDG submissions.

## 6. Area, coverage and missing data

For the five numeric modules, each prepared cell has an eligible area weight `aᵢ` in km², calculated from AOI intersections in EPSG:6933. Drought uses cropland weights; degradation uses terrestrial weights. Other numeric modules use district intersections.

```text
eligible area = sum of all eligible cell weights
valid area = sum of weights for cells with a valid output
coverage (%) = 100 × valid area / eligible area
area-weighted mean = sum(valueᵢ × aᵢ) / valid area
class share (%) = 100 × class area / valid area
```

Differences are `later − earlier` on their common valid footprint. Where a percentage-change layer is supplied, the formula is `100 × (later − earlier) / abs(earlier)`; an earlier value of zero makes percentage change undefined. Numeric zero and negative values are valid data. Missing observations remain NaN/NoData, not zero risk, stable land or no change.

Land-cover/forest calculations use cell-centre allocation and hectares, while numeric diagnostics use fractional intersections and km². Their denominators can differ slightly. **1 km² = 100 ha.** Compare periods, units and denominators before combining results. Time-series district means can also reflect changing valid coverage.

## 7. Export and assemble the review package

| Output | Contents and use |
| --- | --- |
| Layer GeoTIFF | Numeric values, CRS, full analysis grid and NoData. Suitable for QGIS/ArcGIS and further analysis. |
| Map PNG | Illustrated layer with legend, period and source notes. Display colours are not numeric data. |
| Statistics CSV | All result layers in the selected numeric module: units, periods, means, extrema, valid/eligible/missing area and coverage. |
| Class areas CSV | Selected categorical or threshold layer's class areas and shares of valid area. |
| Time series CSV | Selected prepared series, periods, values and coverage where supplied. |
| Categorical exports | Yearly LULC/forest rasters and maps, class areas, transitions, gains/losses and forest metrics. |
| Run manifest JSON | Input hashes, configuration, source/method information, checks and limitations for that run. |
| Diagnostic brief Markdown | Evidence available from all seven modules in the current session, unrun modules, limitations and Step 3 questions. |

For review, retain maps **together with numeric exports and manifests**. A PNG alone cannot reproduce an analysis. The brief does not embed TIFFs or replace the per-module exports. Keep the source citation and describe any changed crosswalk, forest threshold or input package.

## 8. Use your own inputs

### Categorical LULC / forest files

Select **Upload your own GeoTIFFs**, enter distinct years, and provide 1–3 single-band categorical GeoTIFFs. LULC needs 2–3 years; forest can use one. Select **Load raster class codes**, map every observed valid code, and choose target forest classes. Importable crosswalk columns are `source_code,target_code,target_name,color`; colours use `#RRGGBB`, and target codes are 1–999. Code 0 and declared source NoData are excluded.

Optionally add an AOI GeoJSON in WGS84 or one zipped Shapefile containing `.shp`, `.dbf` and `.prj`. Without an AOI, the earliest raster footprint is used. Supported transformations cover WGS84, WGS84 UTM, Web Mercator and EPSG:6933. Convert RGB images, rotated rasters and PixelIsPoint grids in GIS before upload.

Limits: 100 MB and 25 million input pixels per categorical TIFF, eight million analysis cells, 25 MB per vector file, and three periods. Edge width must be at least one analysis cell. Coarsening reduces memory demand; upsampling prepared 50 m data does not restore 30 m detail.

### Prepared numeric packages

Expand **Use a prepared Ganjam data package** in the review section. Select exactly one `nbs-step2/v1` catalog JSON and all required `.tif` files together. The catalog must use the same Ganjam boundary hash, valid provenance, bands, units, grids, area weights and matching SHA-256 hashes. The UI limit is 2 MB for the catalog and 100 MB per TIFF; numeric grids are limited to eight million cells, with an additional aggregate memory budget.

Selecting files does not run the module automatically. Choose a module and run it. **Restore public package** restores the bundled numeric inputs and clears imported numeric results. A custom LULC upload does not update the other five modules, their crop mask or their terrestrial mask. Arbitrary-region numeric acquisition and arbitrary date/scenario selection are not implemented in this release.

## 9. Validation and reproducibility

The Ganjam inputs above are used for real-data integration checks. Small synthetic rasters are also used for tests with known geometric answers; these are software fixtures, not the published environmental maps.

| Check | Recorded evidence |
| --- | --- |
| TypeScript analytical tests | 20 tests covering forest geometry, common footprints, missing/negative/zero values, import validation and export round trips. |
| Python analytical tests | 20 tests including the GIS engine, VHI ranges, dry spells and SOC rounding/incomplete components. |
| GLC-FCS30D browser/Python comparison | 174 numeric comparisons and exact class-pixel agreement across three 6,350,994-cell forest grids. |
| Five numeric modules | 575 arithmetic/area checks across 97 layers: groundwater 4, drought 17, climate 54, flood 5, degradation 17. |
| Climate independent check | Six indices recomputed from daily ACCESS-CM2 values for 1991 and leap year 1992; 12 comparisons. |
| Degradation provider check | Zero disagreements on 141,801 complete/unambiguous baseline cells and 141,804 latest cells; uncertain SOC thresholds and partial observations excluded. |
| Browser workflows | Seven modules run; map context, layer controls, downloads, narrow layout and the GitHub Pages base path checked. |

These tests establish arithmetic and implementation consistency. They do not establish satellite classification accuracy, forecast skill, ecological causality or expert approval. Evidence files and the precise scope are linked in [Step 2 validation](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/docs/step2-validation.md).

For developers, clone the repository and use Node 22.13+ with pnpm. The website needs no Python runtime:

```sh
pnpm install --frozen-lockfile
pnpm dev
pnpm test
pnpm run test:demo
pnpm run test:glcfcs
pnpm run test:step2
pnpm run docs:build
pnpm build
```

For the separate Python engine and scientific tests, create a virtual environment, install `./engine[test,data]`, then run `pytest engine/tests` and `ruff check engine/src engine/tests`. Full source rebuilding, including Earth Engine export names and sequential preparation commands, is documented in the [data preparation guide](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/docs/step2-data.md). Runtime/source responsibilities are implemented in `src/analysis`, `src/step2` and `engine/scripts`.

The canonical English manual is `docs/user-guide.en.md`. `pnpm run docs:build` copies it to `public/guide.en.md` for the website download. The Chinese manual is maintained separately on the owner's local computer and is not included in this release's repository tree or site assets.

## 10. Troubleshooting

| Symptom | Action / explanation |
| --- | --- |
| The map does not show Ganjam clearly | Wait for the boundary status, select Locate study area, and check the study-area label. A basemap-network failure does not prove the analytical boundary failed. |
| Results are lower down the page | Select Overview to return to the retained map. Calculation does not open a separate results page. |
| The overview has no result overlay | Run the selected module, enable Result layer, increase opacity and select a layer/year. Transparent areas can be missing or excluded. |
| A coarse grid looks blocky | This reflects the input scale, particularly 0.25° climate/groundwater. Zooming cannot create local detail. |
| A module shows inputs available but no results | Prepared inputs are not a completed session run. Select Run diagnostic. |
| A hash, band, grid or boundary check fails | Select the matching catalog and all its files, or restore the public package. Do not disable integrity checks. |
| Some differences or VHI values are missing | Review common-period coverage, reference-year requirements and observation masks; do not replace blanks with zero. |
| Flood valid coverage is low | It counts positive mapped inundation after exclusions, not all land known to be safe or unsafe. |
| The worker stops or the page becomes slow | Reduce/crop custom inputs, use a coarser categorical grid, close other heavy tabs or use the separate Python engine. |
| Results disappeared after reload | Results are not a saved account/session. Run again and export files before closing. |
| The deployed page appears outdated | Reload after the GitHub Pages deployment has completed; a cached tab may still hold the previous code. |

## 11. Completion standard and deferred work

The first-release technical standard is **a complete diagnostic supported by public data**: all seven base modules have documented numeric inputs, executable calculations, maps, statistics, machine-readable exports, provenance, coverage/uncertainty notes and Step 3 field-check questions. Land degradation includes all three required subindicators.

Expert acceptance remains separate. Review the class crosswalk and forest definition, local cropping seasons, monsoon observation coverage, climate thresholds/model selection, Trends.Earth period discrepancy, SOC modelling, protection/OECM applicability and local corroborating evidence. Missing protection polygons do not demonstrate absence of protection.

Deferred extensions include authenticated ASIS access, a low-emission climate scenario, automatic acquisition for arbitrary regions, event forecasting, wildfire and other extra hazards, irrigation/salinity/waterlogging extensions, a unified weighted risk score, intervention selection and cost-benefit analysis. The website supports diagnosis and review; it does not automatically choose an NbS intervention.
