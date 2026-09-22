# NbS Diagnostics Lab — User Manual

**Version 0.8 · eight diagnostics in one online workflow · 22 September 2026**

The workspace at [lmqstudio.com/nbs](https://lmqstudio.com/nbs/) combines the seven environmental diagnostics and **Water & productivity** in one online workflow. Choose a study area, select diagnostics, review and run. One analysis can contain both environmental and pyWaPOR calculations, with a shared task history and result selector. Python installation and access codes are not required. **Existing data & advanced tools** is temporarily hidden; its source code and scientific documentation remain available. The GitHub Pages entry forwards visitors to this same online workspace.

[Open the online platform](https://lmqstudio.com/nbs/) · [GitHub repository](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab) · [Download this manual](https://lmqstudio.com/nbs/guide.en.md)

Water & productivity supports **Your study area** with server-acquired satellite and weather inputs, plus the **Fayoum, Egypt** example for **1–31 July 2021**. Select a boundary and dates in the same eight-module workflow; users need no provider accounts. Custom water is limited to a 500 km² enclosing rectangle, 1–31 completed days from 2018 onwards, and 50°S–50°N. The server recomputes every submitted model run. The full Ganjam reference supports seven diagnostics and exceeds the water area limit; use a smaller custom area for water modelling.

The current pyWaPOR thermal-sharpening stage uses ensemble regressions without a fixed random seed. Independent recomputations can differ; retain the exported outputs and run manifest for comparisons. The interface update does not change that modelling behaviour.

This manual explains the online workflow and retains the original advanced-tool instructions for reference. Tests establish software consistency; they do not establish environmental accuracy or local applicability.

## Contents

0. [Submit an online diagnostic](#0-submit-an-online-diagnostic)
1. [Advanced-tool reference](#1-start-a-diagnostic-with-the-advanced-tools)
2. [Understand the map and result controls](#2-understand-the-map-and-result-controls)
3. [Data used for testing](#3-data-used-for-testing)
4. [Where calculations happen](#4-where-calculations-happen)
5. [Module methods](#5-seven-environmental-modules-operation-and-calculation)
6. [Area, coverage and missing data](#6-area-coverage-and-missing-data)
7. [Export and assemble the review package](#7-export-and-assemble-the-review-package)
8. [Use your own inputs](#8-use-your-own-inputs)
9. [Validation and reproducibility](#9-validation-and-reproducibility)
10. [Troubleshooting](#10-troubleshooting)
11. [Completion standard](#11-completion-standard)

## 0. Submit an online diagnostic

1. Open **New analysis**. Your workspace opens automatically. Choose **Your study area**, **Ganjam, India** or **Fayoum, Egypt**, and enter a study-area name. For your own area, upload a simplified GeoJSON or zipped Shapefile, or enter a rectangle.
2. Select **Choose diagnostics**. The eight cards cover land cover, fragmentation, groundwater, drought and vegetation, climate extremes, flood hazard, land degradation, and water and productivity. Source availability is shown on each card. Custom areas within the water limits and the Fayoum example support water modelling; Ganjam uses its recorded seven-module reference inputs.
3. Configure periods and thresholds where available, then select **Review analysis** and **Run analysis**. All selected modules belong to one analysis. Environmental and water calculations use the same boundary but retain their respective observation periods, resolutions and methods. Water sample dates are fixed; custom water dates are editable.
4. Follow **My tasks**. Both old environmental jobs and old water jobs remain available here. Cancel an analysis to stop unfinished child calculations; completed results are retained. You can close the page and return in the same browser. The shared server runs one heavy calculation at a time; a combined analysis may therefore have one module ready while another is still queued or running. Up to two new analyses can be pending per workspace, subject to child-queue limits.
5. Open **Results** or **View results**, choose an analysis, then select its diagnostic. For environmental results, choose **Map layer**; for water results, choose **Map variable** and **Map period**. Review coverage, units, dates, methods and sources. Transparent pixels represent missing or ineligible data. **Partial results** preserve completed outputs and identify missing modules.
6. Download maps, CSV tables, **Run details** or **All results** from the selected module. The environmental result archive includes all environmental modules in that calculation; the water archive includes its water outputs. Environmental rasters use band 1 for results and band 2 for eligible area in km². Water uses multiband period rasters and daily/period CSV files. Results are retained for 30 days. Clearing site data or using another browser opens a separate workspace.

New-area land-cover and forest tasks use **WorldCover 2020 v100 and 2021 v200**, with a selectable 30, 50 or 100 m analysis grid. These releases use different algorithms, so their mapped differences include algorithm effects and are not solely real land-cover change. They do not reproduce the Ganjam GLC-FCS30D three-period analysis. The new-area climate workflow uses **NEX-GDDP-CMIP6 v2.0**, retaining native 0.25° cells. The Ganjam reference retains its recorded v1.1 inputs.

Flood, land degradation, climate, land cover and fragmentation use public source access. New-area MODIS vegetation health is enabled using the server’s configured Earthdata account. A Bhubaneswar workflow test acquired 90 real MODIS files for January 2009–2023 and produced seven result layers. January was selected to test the workflow; choose locally appropriate growing seasons for an assessment. New-area groundwater is also enabled. A Bhubaneswar 2020–2021 test processed all 731 daily native-grid regional subsets (23.5 MB) in about 5.6 minutes, producing four maps and 24 monthly values verified by independent calculation. Two years test the workflow rather than establish a long-term trend; choose a longer record for trend interpretation. The server retains the native 0.25° grid and existing coverage rules. Ordinary users need no NASA account. Existing Ganjam source inputs remain available for recalculation.

Online limits protect the shared server: boundary JSON under 190 KB; enclosing rectangle at most 20,000 km², or 2,000 km² and two million cells for new land-cover/forest tasks; at most 240 annual climate subset requests; 10 GB managed downloads; 12 GB task storage; four hours per task. MODIS checks expected source-download volume before fetching data files. If oversized, submit each growing season separately or reduce the area while retaining at least 15 reference years. Keep meaningful climate periods and split models or indices across tasks rather than shortening periods just to fit. Source outages, missing coverage and limits can prevent completion. A one-year workflow test is software validation, not a defensible climate comparison.

### Online landscape inputs and results

When land cover or forest is selected, **Landscape inputs** has three expandable sections:

1. **Data & years**: keep the available reference maps or upload 1–3 single-band categorical GeoTIFFs (100 MB and 25 million input pixels per file). Choose the correct year for each file and a dataset/version label. Change needs at least two years. All periods must use a consistent source-code legend. Zipped Shapefiles are accepted for AOI and protection polygons, not as land-cover raster inputs.
2. **Class crosswalk & forest definition**: edit source→target codes, class names and colours, or import a CSV (`source_code,target_code,target_name,color`). Identical target codes merge classes. Target 0 excludes a class. Choose the target classes that count as forest. Presets help with WorldCover, ESRI (clouds excluded) and GLC-FCS30D; they do not automatically acquire ESRI or GLC-FCS rasters for a new area.
3. **Protected areas & OECMs**: optionally upload one polygon layer for each, and record source/date/completeness. GeoJSON or one zipped Shapefile is accepted, up to 5 MB of converted GeoJSON. Whole-AOI forest classification precedes stratification. Protected takes priority on overlaps. “Outside supplied polygons” does not establish unprotected status.

Uploaded rasters allow up to eight million aligned analysis cells and a 20,000 km² enclosing rectangle. Public WorldCover acquisition retains its two-million-cell / 2,000 km² limit. Draft uploads expire after 24 hours; submitted sources are pinned through result retention. Files belong to the current browser workspace. No Python is needed on the user's computer.

Results now include period-map comparisons, an explicit change matrix, gross gain/loss/net charts, forest-area charts by spatial group, a full forest metrics table and CSVs. Change always uses cells valid in both years. Zero-denominator derived ratios are missing. Forest patch/edge/core percentages, internal-clearing/forest ratio, TE in km, edge per forest hectare and largest-patch share of forest have explicit units and denominators in the method notes.

**Map PNG** exports the selected map with its legend, source, period and coverage. **Chart PNG** exports each change chart or matrix. **Download brief** at the top of Results creates a printable HTML document covering all eight module statuses, selected results, definitions, sources, coverage and inputs' fingerprints. Open it in a browser and Print → Save as PDF if needed; a Markdown version is also available. The module ZIPs retain full numerical data. Old jobs remain available, but need to be rerun to produce the new change tables and definition metadata.

The [method-differences table](https://lmqstudio.com/nbs/method-differences.md) distinguishes the current boundary, 50 m grid, forest rules, GLDAS/reference-script comparison, VHI/ASIS and climate scenarios/thresholds. The [reference-file checklist](https://lmqstudio.com/nbs/reference-comparison-files.csv) records the files still needed to compare the original assessment.

The calculation formulas below describe the Ganjam reference unless stated otherwise. Sections 1–2, 4 and 7–8 retain the **hidden advanced-tool** controls and local processing as reference; the current online workspace uses the persistent server workflow above. Do not apply the old browser-only file/privacy description to new online uploads: selected source files now go to private server storage for calculation.


## 1. Start a diagnostic with the advanced tools

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

A Web Worker is a computation thread on your device. It is not a remote analysis server. The seven environmental diagnostics do not rerun global climate models, authenticate to Google, launch Earth Engine tasks or call the repository's Python engine. The separate online water workspace sends tasks to its configured server. It can calculate without a custom backend because the program and prepared inputs are downloaded to your browser.

Uploaded file contents are processed locally by the application. Public data and basemap requests still use the network. No Google credentials or service-account keys are shipped with the website. Preparing fresh source data requires separate authorized access and is documented in the [data workflow](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/docs/step2-data.md).

## 5. Seven environmental modules: operation and calculation

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

### 5.8 Water & productivity

**Use:** Choose **Your study area**, enter a rectangle or upload a boundary, select **Water & productivity**, and set the start/end dates. Alternatively choose **Fayoum, Egypt** for the fixed July 2021 example. In Results, choose a map variable and full, monthly or dekadal period. Custom water acquires source products through server-managed accounts. Each task supports at most 31 days and a 500 km² enclosing rectangle, within 50°S–50°N, with completed dates from 2018 onwards.

A real Ganjam pilot at west 84.81, south 19.35, east 84.85, north 19.39 completed source acquisition and modelling for 1–7 January 2021 in about 56 minutes. Days 1–2 had no usable ET/NPP/root-zone output, so complete seven-day maps for those variables correctly remained missing. Reprocessing the same acquired inputs for 3–7 January produced complete coverage in that test. This is workflow evidence, not a guarantee of coverage, identical recomputation or runtime in other areas.

**If the map is empty:** review **Valid area coverage** and the daily chart/CSV. Period maps require every selected day at each pixel; a gap can invalidate a period total even when other days have results. The page explains this condition, and daily outputs remain downloadable. Choose a suitable observed period; missing values are never filled with zero.

pyWaPOR 3.7.3 runs SE_ROOT v3 and ETLook v3 on the nominal 60 m sample input grid. The four primary map variables are evapotranspiration (ET), reference ET, net primary production (NPP) and relative root-zone saturation. Downloads retain all eight output variables, including evaporation, transpiration, interception and AETI. ET = evaporation + transpiration; AETI also includes interception. NPP is carbon production in gC/m², not crop yield or dry biomass. Root-zone saturation is dimensionless, not measured volumetric soil moisture.

Water and NPP period totals require every daily value at a pixel; saturation uses a complete-period mean. Missing days remain missing. Partial calendar periods are labelled as selected days. Summaries use geodesic pixel areas with a pixel-centre boundary mask and include all land-cover types in the boundary, without a crop mask. Thermal sharpening uses an unseeded ensemble fit, so repeated runs can differ even with identical inputs. Retain source hashes, settings and outputs together; this module does not yet calculate a crop yield gap or crop-specific water productivity ratio.

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

The following table describes the retained advanced-tool exports. For currently available online downloads, use section 0 and the buttons in Results. The online workflow does not yet provide a single eight-module brief or map PNG export.

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

Use **Create Python package** to choose a region, five numeric modules and their periods/scenarios/seasons, then download a configured Python package. Run it locally and select **Import local results** to load its `results.zip`. See the [local preparation guide](local-preparation.en.md) for installation, NASA account requirements, calculations and troubleshooting.

You may also select `catalog.json`, its named boundary GeoJSON and all referenced `.tif` files together. Boundary and raster SHA-256 values must match the catalog. The imported boundary replaces the shared study area; previous numeric and categorical results are cleared. Unselected or failed modules stay unavailable. The two categorical modules use this boundary and require matching uploaded rasters. **Restore Ganjam example** restores the original boundary and bundled inputs.

Imported files stay in browser memory. Run a module after import to inspect its layers and statistics. Refreshing the page clears the imported session. Limits are 2 MB per catalog, 10 MB per boundary, 100 MB per TIFF, eight million cells per grid and forty million input-plus-output cells per module. ZIP limits are 200 MB compressed and 350 MB unpacked. Legacy Ganjam catalog-plus-TIFF imports can use the bundled boundary if its hash matches.

## 9. Validation and reproducibility

The Ganjam inputs above are used for real-data integration checks. Small synthetic rasters are also used for tests with known geometric answers; these are software fixtures, not the published environmental maps.

| Check | Recorded evidence |
| --- | --- |
| TypeScript analytical and workflow tests | 33 tests covering forest geometry, common footprints, imports, sessions, checksums and eight-module request construction. |
| Python analytical tests | 34 tests including the GIS engine, VHI, dry spells, SOC rules, MODIS download budgeting and native-grid GLDAS daily readers. |
| Online service tests | 26 tests covering ownership, durable queues, sessions, shared boundaries, cancellation, limits and restart recovery. |
| GLC-FCS30D browser/Python comparison | 174 numeric comparisons and exact class-pixel agreement across three 6,350,994-cell forest grids. |
| Five numeric modules | 575 arithmetic/area checks across 97 layers: groundwater 4, drought 17, climate 54, flood 5, degradation 17. |
| Climate independent check | Six indices recomputed from daily ACCESS-CM2 values for 1991 and leap year 1992; 12 comparisons. |
| Degradation provider check | Zero disagreements on 141,801 complete/unambiguous baseline cells and 141,804 latest cells; uncertain SOC thresholds and partial observations excluded. |
| Browser workflows | Seven modules run; map context, layer controls, downloads, narrow layout and the GitHub Pages base path checked. |
| Unified v0.7 production workflow | Ganjam seven-module run and Fayoum water + degradation run completed; 140 maps and 148 result-file hashes verified. See [online validation](https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/blob/main/docs/online-validation.md) for the scope and water repeatability note. |

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

The canonical English manual is `docs/user-guide.en.md`. `pnpm run docs:build` copies it to `public/guide.en.md` for the website download.

## 10. Troubleshooting

These entries apply to the current online workspace. Earlier sections identify controls that belong to the hidden advanced tools.

| Symptom | Action / explanation |
| --- | --- |
| The map does not show the area clearly | Wait for the boundary preview, use Locate study area, and check the study-area label. A basemap-network failure does not prove the analytical boundary failed. |
| The analysis is still running | Check My tasks. Computation continues after closing the page; one heavy calculation runs at a time. |
| A result overlay is missing | Open Results, choose a completed diagnostic and a map layer, and check opacity and coverage. Transparent areas can be missing or excluded. |
| A coarse grid looks blocky | This reflects the input scale, particularly 0.25° climate/groundwater. Zooming cannot create local detail. |
| Water is unavailable for the selected region | Use Your study area with a ≤500 km² enclosing rectangle within 50°S–50°N, or the Fayoum example. The full Ganjam reference is too large for the water pilot. |
| Water calculation completed but a map has no data | Check daily coverage. A complete-period map needs every selected day at each pixel; gaps remain missing. Daily results may still be available in the chart and downloads. |
| A hash, band, grid or boundary check fails | Retry the download. If it still fails, report the task identifier so the administrator can inspect the result. Do not disable integrity checks. |
| Some differences or VHI values are missing | Review common-period coverage, reference-year requirements and observation masks; do not replace blanks with zero. |
| Flood valid coverage is low | It counts positive mapped inundation after exclusions, not all land known to be safe or unsafe. |
| One diagnostic did not complete | Other completed results remain available. Review the displayed source/coverage reason; administrators can inspect the private worker log. |
| A job exceeds resource limits | Use a smaller study area or split models, indices or growing seasons while retaining meaningful reference periods. |
| My tasks appears empty | Return to the same browser and site. Clearing site data or using another browser opens a new workspace. Results expire after 30 days. |
| The deployed page appears outdated | Reload the server platform. GitHub Pages forwards to it; a GitHub push does not redeploy the compute service. |

## 11. Completion standard

The technical standard is **a complete diagnostic supported by public data**: documented inputs, executable calculations, maps, statistics, machine-readable exports, provenance and coverage/uncertainty notes. All seven Ganjam environmental modules, the Fayoum water example and the bounded custom-water workflow meet that execution standard within their stated source and region limits. Land degradation includes all three required subindicators. This standard does not imply that every retained advanced-tool feature has already been migrated to the online workflow.
