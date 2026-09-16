# NbS GIS Diagnostics Lab

An English-language Ganjam Step 2 workspace for public-data environmental screening. The static frontend runs on GitHub Pages; Python and Earth Engine prepare the public inputs. No credentials or analysis server are embedded in the website.

Version **0.4.0** implements all seven base modules. Technical calculations are separate from expert acceptance, protected-area/OECM applicability and field verification.

**[Open the website](https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/)** · **[Read the English user manual](docs/user-guide.en.md)** · [Download the manual](https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/guide.en.md)

The manual covers operation of every module, the real Ganjam public datasets used for testing, calculation formulas, exports and interpretation limits. The Chinese manual is kept locally by the project owner and is excluded from this release's repository tree and website.

| Module | First-release public inputs | Main outputs |
| --- | --- | --- |
| Land-cover change | GLC-FCS30D 2002 / 2012 / 2022, 30 m source on a 50 m equal-area grid | Editable ten-class crosswalk, three pairwise transitions, gains/losses, class areas |
| Forest fragmentation | Same three land-cover maps; forest includes mangroves, excludes orchards | Core, edge, patch, internal clearing; patch/edge/shape metrics; optional protection/OECM strata |
| Groundwater | GLDAS 2.2 daily GWS, February 2003–December 2023, native 0.25° | Monthly series, 2003–2013 / 2014–2023 means, change, Theil–Sen trend |
| Drought / vegetation stress | MOD13A2.061 + MOD11A2.061, 2001–2023 seasonal reference, fixed 2022 crop mask | Kharif/Rabi VHI for 2013 and 2023, common-footprint change, seasonal series, observation coverage |
| Climate extremes | NEX-GDDP-CMIP6 v1.1, three models, native 0.25° | Six indices; 1991–2020 vs 2040–2069; SSP2-4.5 / SSP5-8.5; model range and annual series |
| River flood hazard | JRC/CEMS-GloFAS v2.1.2, 3 arc seconds | 10-, 100-, 500-year depths; inundated area; permanent-water and spurious-depth flags |
| Land degradation | Trends.Earth SDG 15.3.1 v1.2 | All three subindicators, SOC percentage change, one-out-all-out, component completeness, baseline and 2023 status |

Drought is a **MODIS seasonal alternative**, not FAO ASIS. Climate scenarios differ from the reference report’s RCP2.6. Land-degradation periods follow the publisher, including the documented discrepancy between its latest land-cover/SOC record (2015–2022) and TIFF labels (2015–2023). Full methods and limitations are in the catalog and [English user manual](docs/user-guide.en.md).

## Run locally

Use Node 22.13+ and pnpm:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Choose a module and run it. The overview shows Ganjam’s boundary and selected result; switching modules retains the map. Land cover and forest share one configurable run. Other modules use the prepared numeric package. Export GeoTIFF, PNG, CSV, time series and JSON manifests, then download the diagnostic brief to assemble session evidence for review.

The complete public diagnostic inputs occupy roughly **4.5 MB compressed**, excluding the retained WorldCover regression example. Native coarse grids remain coarse. Maps do not imply village-scale precision.

## Execution and data handling

- Earth Engine / Python: source acquisition, provider quality filtering, temporal aggregation, model indices and public data preparation.
- Browser Web Workers: input hashes, categorical alignment/reclassification, forest analysis, continuous-map arithmetic, subindicator combination and weighted statistics.
- GitHub Pages: static code, prepared public rasters and provenance. The website does not authenticate to Google or launch cloud work.
- Uploaded files: local processing. Input limits, grid checks, band checks and memory budgets reject unsupported packages.

Continuous-module area weights use AOI intersections in square kilometres. Crop and terrestrial modules use documented eligible-area masks. The land-cover engine uses cell-centre allocation. Zero and negative values are valid numeric data; NoData never becomes stable land, no drought or safe floodplain.

For a new numeric package, select one `nbs-step2/v1` catalog JSON and its TIFFs in the review section. The current numeric workspace requires the same Ganjam boundary hash. Land-cover uploads retain the existing custom-AOI workflow. Changing one module’s source does not silently change the others.

## Validation

```sh
pnpm test
pnpm run test:demo       # retained two-period WorldCover regression
pnpm run test:glcfcs     # actual three-period land-cover/forest package
pnpm run test:step2      # all five numeric packages and 97 result layers
pnpm build
python -m pip install -e './engine[test,data]'
pytest engine/tests
ruff check engine/src engine/tests
```

The public validation files record Python/browser agreement, full forest-class pixel hashes, numeric band summaries and class-area conservation. Climate annual indices were independently recomputed from daily values for a normal and leap year. Land-degradation combinations are checked against the published indicator on complete observations; integer SOC values exactly ±10% remain uncertain because rounding can cross the threshold.

These checks validate software and data handling, **not environmental attribution or field accuracy**. See [data preparation and reproducibility](docs/step2-data.md), [validation evidence](docs/step2-validation.md) and the separate [Python engine guide](engine/README.md).

## Review gate and deferred work

Seven prepared modules do not mean expert signoff. Review the class crosswalk, forest definition, cropping calendars, climate thresholds, source-period discrepancy, protection/OECM applicability and Step 3 field questions. Missing protection polygons do not establish that land is unprotected.

Deferred: automatic arbitrary-AOI acquisition, restricted ASIS access, low-emission climate scenario, event forecasting, a single weighted risk score, additional hazards, intervention selection and cost-benefit analysis. No reviewed status is fabricated.

## Sources and deployment

Sources, versions, licences and attribution accompany every module in [the data catalog](public/data/step2/catalog.json). Boundary: geoBoundaries gbOpen IND ADM2 (2021), ODbL 1.0. Basemap: OpenStreetMap contributors. Source authors retain their rights; modified public inputs are attributed in the catalog.

The previous ESA WorldCover 2020/2021 package remains under `public/data/worldcover` for regression testing. Its algorithms differ between years, so it is not the default diagnostic series.

Only cropped public data and non-sensitive provenance belong in Git. Raw inputs and signed Earth Engine download links remain in ignored `engine/outputs`; transient links are deleted after acquisition. Pushes to `main` run checks, build and deploy through the existing GitHub Pages workflow.

Maintain the English manual in `docs/user-guide.en.md`. `pnpm run docs:build` creates the identical website download at `public/guide.en.md`; both build commands run that step automatically.
