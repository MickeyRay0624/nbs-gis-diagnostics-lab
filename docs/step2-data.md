# Ganjam Step 2 data workflow

This is the retained reference-package preparation workflow. The v0.7 online service now also acquires and computes new-area environmental inputs on the server; see [service deployment](../services/pywapor/README.md). The browser-only controls described below belong to the temporarily hidden advanced tools.

The first release targets a complete diagnostic using public data for seven modules: land-cover change, forest fragmentation, groundwater storage, drought / vegetation stress, climate extremes, river flooding and land degradation. Outputs are technical screening evidence. Expert acceptance, protection applicability and unresolved data gaps remain visible.

## Execution

Source preparation runs outside the website, in Python or Earth Engine. It crops numeric rasters, applies documented provider quality masks and generates fractional AOI area weights. GitHub Pages serves these prepared files. A browser Web Worker verifies each SHA-256 hash, decodes the GeoTIFF, calculates differences / relative changes / subindicator combinations, and computes area-weighted summaries. Uploads remain on the device. The website does not possess Google credentials or launch cloud jobs.

The overview map remains mounted while modules run. Raster previews are reprojected to Web Mercator for display; the exported numerical grid retains its source resolution. Image stretching never changes the analysis resolution.

## Numeric package

`public/data/step2/catalog.json` follows `nbs-step2/v1`. Each raster has a filename, checksum, EPSG code, grid, band meanings, native resolution, source and preparation method. Bands are one-based. Every raster includes a non-negative, finite AOI-intersection area band in square kilometres. Data NoData is NaN, while zero and negative values remain valid. Areas outside the AOI have weight zero. Compared grids and area weights must match exactly within numeric tolerance.

The catalog records all seven modules, including unavailable inputs. Availability means a numeric package is present, not that the diagnosis has passed expert review. Never replace missing observations with zero risk or stable land. A soil-carbon baseline alone is insufficient to declare soil-carbon change.

Local packages can be selected through the review section. Select exactly one catalog JSON plus its TIFF files. The first release validates against the supplied Ganjam boundary hash. Each TIFF is limited to 100 MB and each grid to eight million cells.

## Prepare public flood inputs

Install the Python engine and `requests`, then run:

```sh
# Initialize only when no catalog exists:
python engine/scripts/init_step2_catalog.py
python engine/scripts/prepare_step2_flood.py
```

The flood builder reads official JRC v2.1.2 tiles through HTTP range requests. It retains 10-, 100- and 500-year positive inundation depths and permanent-water / spurious-depth flags. Tile grids are aligned by nearest neighbour to a common 3-arc-second grid. The AOI boundary weights are calculated in EPSG:6933. Raw depth NoData remains unknown; it is not counted as proven dry or safe land. The statistics explicitly separate mapped inundation area from the full AOI denominator. Python reference summaries accompany the public raster.

## Earth Engine project

The dedicated Cloud project is `nbs-ganjam-diagnostics`. On 16 September 2026 the project was created, the Earth Engine API was enabled and noncommercial Community registration was completed for the user's confirmed personal research / learning use. The Console showed eligibility through 16 March 2028. This registration does not establish access to restricted FAO collections. Dataset access must be tested independently.

Do not put OAuth tokens, service-account keys, download tokens or signed export links in this repository or the website. Source preparation should record stable dataset identifiers and versions, not authentication material.

## Completion gate

All seven diagnostics need source-verified numeric inputs, reproducible processing, maps, machine-readable outputs, coverage statistics, limitations and Step 3 field-check questions. All three land-degradation subindicators must be represented. Protection / OECM applicability and expert review must be documented separately. Optional hazards, additional AOIs, intervention selection, cost-benefit analysis and a single weighted risk score are outside this first-release gate.

## Rebuild the complete Ganjam package

Install the engine with the `data` extra. Run the checked-in `gee_*.js` scripts in the authenticated Earth Engine Code Editor. EPSG:6933 is supplied as WKT because the Code Editor export service did not parse that EPSG identifier directly. Downloads are split into bounded requests; the page itself never requires a Google account.

| Script | Export / preparation |
| --- | --- |
| `gee_lulc.js` | Three GLC-FCS30D bands at 50 m; save as `glcfcs-2002-2012-2022.tif` |
| `gee_groundwater.js` | Yearly monthly-mean GLDAS files, `gldas-2003.tif` … `gldas-2023.tif` |
| `gee_drought.js` | Yearly MODIS seasonal value/coverage bands, `modisqa-2001.tif` … `modisqa-2023.tif` |
| `gee_climate.js` | Six annual indices in ten-year chunks, three models and two scenarios |
| `gee_climate_validation.js` | Daily normal/leap-year samples and verified model licence/version properties |
| `prepare_step2_lulc.py` | Public fine-code TIFFs, crosswalk and independent Python land-cover/forest reference |
| `prepare_step2_groundwater.py` | Means, change inputs, annual Theil–Sen trend and monthly series |
| `prepare_step2_drought.py` | Quality checks, same-season VHI, fixed crop-area weights and coverage layers |
| `prepare_step2_climate.py` | 30-year model means, ensemble means, model spread and annual series |
| `prepare_step2_flood.py` | Direct public JRC COG range reads, depths and quality flags |
| `prepare_step2_degradation.py` | Direct Trends.Earth COG crop; subindicator classes, published reference and completeness |

Raw export files go in ignored `engine/outputs/step2-source`. `download_gee_exports.py` accepts a transient JSON mapping local output stems to Code Editor download URLs; it checks downloaded TIFFs and deletes that JSON after use. It does not authenticate or persist credentials. Keep download URLs out of committed files.

Run preparation sequentially to avoid concurrent catalog writes:

```sh
python engine/scripts/prepare_step2_lulc.py
python engine/scripts/prepare_step2_groundwater.py
python engine/scripts/prepare_step2_drought.py
python engine/scripts/prepare_step2_climate.py
python engine/scripts/prepare_step2_flood.py
python engine/scripts/prepare_step2_degradation.py
python engine/scripts/validate_step2_climate.py
pnpm run test:glcfcs
pnpm run test:step2
pnpm exec tsx scripts/generate-guide.ts
```

The public inputs can be validated offline from a checkout; rebuilding raw exports requires Earth Engine access or the original source files. The Earth Engine Community project used for preparation has a limited compute allowance; these are manual preparation scripts, not recurring jobs.

### Scientific choices that remain visible

- **Land cover:** three adjacent/end-point comparisons, consistent product, explicit ten-class crosswalk. Forest/mangrove grouping is an analytical definition. The 50 m browser grid loses some 30 m detail.
- **Groundwater:** first available month is February 2003. Monthly means require 90% daily completeness, period means 90% monthly completeness. Native 0.25° regional storage in mm is not groundwater-table depth.
- **Drought:** ASIS was inaccessible, so this package uses equal-weight seasonal VCI/TCI. NDVI QA accepts good/marginal observations; LST requires good mandatory QA and ≤2 K reported error. Seasonal thresholds retain ≥30% NDVI and ≥20% LST composites, with at least 15 reference years. An initial 50%-availability rule left no usable monsoon temperature reference; coverage maps now make the sparse clear-sky sampling explicit. Seasons and quality choices need review. Fixed crop weights are summed from fine-grid AOI intersections.
- **Climate:** six threshold/mean indices, three models, two available future scenarios. Native grid, all-year completeness, no combined risk score. All selected image-property histograms reported version 1.1 and CC-BY-4.0, with no `interpolated=true` flags over the inspected 1991–2069 window. Individual-model climatologies are retained in the 96-band input asset.
- **Flood:** positive modelled depth is mapped inundation. Blank depth cells cannot establish safety; permanent water and suspicious depth flags are separate layers. No storm-surge or urban-drainage inference.
- **Degradation:** publisher subindicators are retained rather than inventing a SOC trend from a static baseline. Latest productivity is 2008–2023, LC/SOC 2015–2022 according to the dataset record. TIFF labels disagree by one year; provenance retains that discrepancy. Integer SOC at exactly ±10% is uncertain because of rounding. Known degradation with another component missing is a conservative screening flag, distinguished by the completeness layer. Publisher agreement is tested only where every component is available.

`validation.json` describes browser/Python band-summary and arithmetic checks. `degradation-provider-validation.json` records comparison with the published indicator. `climate-daily-validation.json` compares independent daily NumPy calculations against Earth Engine annual outputs. These are software checks, not ecological validation.
