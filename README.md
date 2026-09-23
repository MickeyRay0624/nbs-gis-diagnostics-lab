# NbS GIS Diagnostics Lab

An English-language Step 2 workspace for public-data environmental screening. The online platform runs seven diagnostics and pyWaPOR on a compute service with automatic browser workspaces, with persistent jobs and results. Users need only a browser. Provider credentials remain on the server.

Version **0.8.0** unifies all eight diagnostics in one study-area → module selection → review and submit flow. A durable parent analysis links environmental and water queues, recovers unfinished dispatch after API restart, and exposes existing jobs in a shared history. The page has been redesigned for desktop and mobile; Existing data & advanced tools is temporarily hidden. Server computation for all seven Ganjam diagnostics and public-source acquisition for new areas remain available. New-area MODIS vegetation health is enabled after authenticated 15-year source and calculation tests. New-area GLDAS groundwater uses verified regional native-grid subsets; its authenticated 2020–2021 test processed 731 daily files and produced four maps and 24 monthly values. The combined pilot is deployed at [lmqstudio.com/nbs](https://lmqstudio.com/nbs/). GitHub Pages forwards visitors to that same workspace so browser sessions and results use one host.

**[Open the website](https://lmqstudio.com/nbs/)** · **[Read the English user manual](docs/user-guide.en.md)** · [Download the manual](https://lmqstudio.com/nbs/guide.en.md)

The manual covers operation of every module, the real Ganjam public datasets used for testing, calculation formulas, exports and interpretation limits. 

| Module | Reference public inputs | Online outputs |
| --- | --- | --- |
| Land-cover change | GLC-FCS30D 2002 / 2012 / 2022, 30 m source on a 50 m equal-area grid | Fixed ten-class reference crosswalk, three pairwise transitions and class areas |
| Forest fragmentation | Same three land-cover maps; forest includes mangroves, excludes orchards | Core, edge, patch, internal clearing; whole-landscape patch/edge/shape metrics |
| Groundwater | GLDAS 2.2 daily GWS, February 2003–December 2023, native 0.25° | Monthly series, 2003–2013 / 2014–2023 means, change, Theil–Sen trend |
| Drought / vegetation stress | MOD13A2.061 + MOD11A2.061, 2001–2023 seasonal reference, fixed 2022 crop mask | Kharif/Rabi VHI for 2013 and 2023, common-footprint change, seasonal series, observation coverage |
| Climate extremes | NEX-GDDP-CMIP6 v1.1, three models, native 0.25° | Six indices; 1991–2020 vs 2040–2069; SSP2-4.5 / SSP5-8.5; model range and annual series |
| River flood hazard | JRC/CEMS-GloFAS v2.1.2, 3 arc seconds | 10-, 100-, 500-year depths; inundated area; permanent-water and spurious-depth flags |
| Land degradation | Trends.Earth SDG 15.3.1 v1.2 | All three subindicators, SOC percentage change, one-out-all-out, component completeness, baseline and 2023 status |
| Water & productivity | FAO Fayoum sample provider inputs, 1–31 July 2021; pyWaPOR 3.7.3 | ET, reference ET, NPP and root-zone saturation maps; daily/period summaries and model outputs |

The first seven rows describe **Ganjam reference data**; the water row describes **Fayoum**. Eight selectable modules do not mean all eight currently support every region. The online flow accepts bounded categorical GeoTIFFs, explicit years, editable class crosswalks, forest definitions and protection/OECM polygons. See [online capability gaps and next steps](docs/online-workflow-gaps.md) and [production validation](docs/online-validation.md).

Drought is a **MODIS seasonal alternative**, not FAO ASIS. Climate scenarios differ from the reference report’s RCP2.6. Land-degradation periods follow the publisher, including the documented discrepancy between its latest land-cover/SOC record (2015–2022) and TIFF labels (2015–2023). Full methods and limitations are in the catalog and [English user manual](docs/user-guide.en.md).

### Online water and productivity

Open **New analysis**, choose **Fayoum, Egypt** and select **Water & productivity** alongside any other desired diagnostics. Submit once and view maps and time series through the unified **Results** page. Tasks continue on the server after the page closes. Alternatively choose **Your study area**, select Water & productivity and set your dates. Custom source acquisition is enabled using server-managed NASA, CDSE and CDS accounts. Tasks support a 500 km² enclosing rectangle and 1–31 completed days from 2018 onwards, within 50°S–50°N. Cloud gaps can leave daily or complete-period outputs missing; review coverage. See [service deployment and limits](services/pywapor/README.md).

### Online environmental diagnostics

The unified eight-module **New analysis** flow is the default. Recompute all seven modules from verified Ganjam inputs, or submit a new boundary for server-side source acquisition and calculation. New-area public land-cover/forest inputs are WorldCover 2020/2021; their algorithm differences must be considered when interpreting mapped change. The Ganjam reference retains its original inputs and source periods. A separate NumPy 2 worker avoids changing pyWaPOR's compatible environment. Both workers share one compute lock; all modules in a combined analysis must use the same boundary. Tasks retain complete or explicitly partial results, downloads and provenance for 30 days.

## Run locally

Use Node 22.13+ and pnpm:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

The online UI needs a configured API. For local development, run the API with a local persistent data directory, `NBS_PUBLIC_ACCESS=true`, `NBS_SECURE_COOKIE=false`, cookie path `/api` and an explicit localhost origin; set `VITE_NBS_API_URL=http://localhost:8021/api` for the frontend. See [service setup](services/pywapor/README.md). The hidden advanced workspace remains in `src/step2/Workspace.tsx`; there is currently no public UI entry for using it without the service.

The complete public diagnostic inputs occupy roughly **4.5 MB compressed**, excluding the retained WorldCover regression example. Native coarse grids remain coarse. Maps do not imply village-scale precision.

## Execution and data handling

- Earth Engine / Python: source acquisition, provider quality filtering, temporal aggregation, model indices and public data preparation.
- Browser Web Workers: input hashes, categorical alignment/reclassification, forest analysis, continuous-map arithmetic, subindicator combination and weighted statistics.
- Online workspaces: server source acquisition, all numerical calculations, persistent queues and result storage. The browser renders selected output layers and verifies their checksums.
- Static hosting: frontend, prepared public rasters and provenance. The advanced workspace code retains optional browser/local preparation tools; its UI entry is temporarily hidden.
- The online wizard accepts a boundary GeoJSON, zipped Shapefile or rectangle, then the server acquires source rasters. Land-cover and forest tasks can instead use uploaded categorical GeoTIFFs, a crosswalk and protection/OECM polygons; calculations run on the server.

Continuous-module area weights use AOI intersections in square kilometres. Crop and terrestrial modules use documented eligible-area masks. The land-cover engine uses cell-centre allocation. Zero and negative values are valid numeric data; NoData never becomes stable land, no drought or safe floodplain.

The optional portable Python toolkit and its import workflow remain in source for GIS users, although their advanced UI entry is hidden. The [local preparation guide](docs/local-preparation.en.md) documents choices, data, accounts, calculations, limits and actual test coverage. No platform backend or Earth Engine project is needed for that toolkit. Groundwater/MODIS in the optional local toolkit require the user's NASA Earthdata account. Ordinary online users use the configured server accounts and do not install Python.

## Validation

```sh
pnpm test
pnpm run test:demo       # retained two-period WorldCover regression
pnpm run test:glcfcs     # actual three-period land-cover/forest package
pnpm run test:step2      # all five numeric packages and 97 result layers
pnpm build
python -m pip install -e './engine[test,data]'
pytest engine/tests
ruff check engine/src engine/tests engine/localprep
```

The public validation files record Python/browser agreement, full forest-class pixel hashes, numeric band summaries and class-area conservation. Climate annual indices were independently recomputed from daily values for a normal and leap year. Land-degradation combinations are checked against the published indicator on complete observations; integer SOC values exactly ±10% remain uncertain because rounding can cross the threshold.

These checks validate software and data handling, **not environmental attribution or field accuracy**. See [data preparation and reproducibility](docs/step2-data.md), [validation evidence](docs/step2-validation.md) and the separate [Python engine guide](engine/README.md).

## Interpretation and remaining work

Calculations and checks establish implementation consistency; local forest definitions, crop calendars, climate thresholds and observations determine how results should be interpreted. Missing protection polygons do not establish that land is unprotected. These are interpretation considerations, not an additional approval step for using the platform.

New-area acquisition is available for the seven environmental diagnostics within documented limits. Custom-region water acquisition is enabled after a fresh Ganjam acquisition/model/export run and a complete-period reprocessing check. Land-cover uploads, protection statistics, comparison charts and printable briefs are available online. Independent comparison with the original assessment still needs the files listed in the [comparison intake checklist](docs/reference-comparison-files.csv). ASIS, low-emission climate scenarios, additional hazards, suitability scoring, intervention selection and cost-benefit analysis are separate extensions; they are not implied by the eight-module release.

## Sources and deployment

Sources, versions, licences and attribution accompany every module in [the data catalog](public/data/step2/catalog.json). Boundary: geoBoundaries gbOpen IND ADM2 (2021), ODbL 1.0. Basemap: OpenStreetMap contributors. Source authors retain their rights; modified public inputs are attributed in the catalog.

The previous ESA WorldCover 2020/2021 package remains under `public/data/worldcover` for regression testing. Its algorithms differ between years, so it is not the default diagnostic series.

Only cropped public data and non-sensitive provenance belong in Git. Raw inputs and signed Earth Engine download links remain in ignored `engine/outputs`; transient links are deleted after acquisition. Pushes to `main` run frontend, Python-engine and online-service checks. The Pages build publishes an entry pointing to the same-origin online workspace, plus static documentation and public reference assets. It does not redeploy the Ubuntu compute service. `pnpm build` produces the application; `pnpm run build:pages` additionally replaces the Pages landing document with the forwarder.

Maintain the English manual in `docs/user-guide.en.md`. `pnpm run docs:build` creates the identical website download at `public/guide.en.md`; both build commands run that step automatically.

## Online landscape migration (0.8)

The unified workspace accepts custom categorical GeoTIFFs and years, CSV crosswalks, forest definitions and protected/OECM polygon layers. It computes change matrices, gross gains/losses, forest spatial-group metrics and common-coverage comparisons on the server. Results include PNG maps/charts and a unified printable HTML/Markdown brief. See the [method-differences table](docs/method-differences.md) and [original-assessment file checklist](docs/reference-comparison-files.csv). Custom water areas are enabled within the service limits. The [validation record](docs/online-validation.md) distinguishes fresh acquisition, complete-period model checks and source-coverage gaps.
