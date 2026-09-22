# Online workflow validation

## v0.8 landscape migration — 22 September 2026

The production workspace now accepts one to three categorical GeoTIFFs with explicit years, class crosswalks, forest definitions and optional protected/OECM polygons. It publishes change matrices, gross gain/loss/net and forest-group charts, period-map comparisons, PNG export and a combined HTML/Markdown brief. The retained advanced-tools entry is still hidden.

| Check | Evidence |
| --- | --- |
| Frontend unit tests | 37 passed, including high source-code collision prevention and safe brief rendering/statuses. TypeScript and the production build passed. |
| Online service tests | 32 passed, including ownership, upload validation/limits/expiry, source integrity, common-coverage change, strata conservation and a three-period upload-to-result integration. |
| Existing Ganjam results | All 9 land/forest map statistics and every original forest-metric field exactly matched the previous production run for the same 2002/2012/2022 inputs and definitions. Added metrics and charts do not change those earlier values. |
| Live HTTPS upload and calculation | Three real Ganjam GLC-FCS30D subsets, each 320,626 bytes, passed the dedicated large-body upload route. The custom-area job produced 9 maps and 5 tables with 15 computation checks. |
| Protection/OECM overlap | The live job used explicitly labelled artificial overlapping polygons to test allocation. Forest areas summed across disjoint strata, and gross gain minus gross loss equalled net change. These polygons do not establish actual protected status in Ganjam. |
| Live result integrity | All 23 downloadable files passed byte-size and SHA-256 checks through the production HTTPS API. |
| Browser checks | Production three-step input flow and local completed results were inspected at 1280 px; the result page also had no document overflow at 319 px. Map/chart export controls, matrix rendering and the printable brief were checked. The map and gain/loss PNG files were downloaded and visually inspected. |
| Provider setup | ERA5 terms were accepted with the account owner's explicit authorization. A real CDS request returned a valid 25,171-byte NetCDF with `t2m`. CDSE authentication returned `Account is not fully set up`; the official login returned to the email-activation page. |

The fresh custom-water model run remains blocked by CDSE email activation. `NBS_ENABLE_CUSTOM` remains false; this release does not claim that arbitrary-region water computation has passed. All provider secrets are confined to the server's private environment, outside source control and result files.

The original-assessment comparison remains dependent on the files in [the comparison intake checklist](reference-comparison-files.csv). The [method differences](method-differences.md) include the baseline boundary/grid, forest denominators, GLDAS/GEE comparison status, VHI versus ASIS, and the differing climate periods and dry-spell definitions.

## v0.7 integration baseline

22 September 2026. This release publishes the already deployed eight-module workspace, compute services and portable data-preparation code. The GitHub Pages entry forwards to the canonical online platform at <https://lmqstudio.com/nbs/>. A GitHub push does not redeploy the Ubuntu containers.

## Automated checks

| Check | Result and scope |
| --- | --- |
| Frontend tests | 33 passed: categorical arithmetic, masks, imports, result integrity, browser sessions and combined requests. |
| Python engine tests | 34 passed: GIS/forest processing, VHI, climate indices, SOC rules, GLDAS readers, download budgeting and missing data. Ruff passed. |
| Online API tests | 26 passed: sessions, isolation, limits, queues, idempotency, shared-area validation, cancellation and restart recovery. |
| WorldCover regression | 91 numeric checks; 12,701,988 fragmentation pixels agree with the saved independent Python reference. |
| Three-period GLC-FCS30D regression | 174 numeric checks; 19,052,982 fragmentation pixels agree with the saved Python reference. |
| Five numeric modules | 575 arithmetic/area checks across 97 prepared reference layers. |
| Optional local-package integration | 274 checks across 37 layers from a previously acquired Bhubaneswar package. This requires local output files and is not a clean-checkout CI test. |

The GitHub workflows run frontend/reference checks, engine lint/tests and online service tests. Provider credentials are not required by CI. Real model runs and authenticated downloads are integration evidence, not performed on every push.

Local checks emitted dependency deprecation notices and a NumPy extension ABI-size warning in the engine environment; no test failed. The deployed numerical environments are separate and pinned. Passing arithmetic tests does not replace dependency compatibility review when changing those environments.

## Production integration evidence

The deployed v0.7 workspace completed a Ganjam seven-module analysis and a Fayoum combined water + degradation analysis. The latter proves that one parent submission dispatches both queues for one boundary; it is not an eight-module analysis over Ganjam.

| Run | Completed outputs |
| --- | --- |
| Ganjam seven environmental modules | 106 map layers, 114 files, 109 export checks; numeric layers matched the previous seven-module run. |
| Fayoum land degradation | 14 map layers, 20 files, 14 checks. |
| Fayoum water | 20 map/period combinations, 14 files, 27 checks. |

All 148 files had their recorded sizes and SHA-256 verified on the host. Twelve representative files were also downloaded through the actual HTTPS API: GeoTIFF, CSV, result ZIP and manifest for each child. Rate-limited verification used backoff after an initial dense download attempt encountered the existing request limit.

Browser checks covered 390, 768 and 1280 px widths, actual submission, result selection, history restoration after refresh, old water results, map/period changes and downloads. No horizontal overflow or browser error was observed in that acceptance run. Queues were idle after completion. Runtime and area limits are recorded in the [service guide](../services/pywapor/README.md).

## Water repeatability

The old and new Fayoum runs had matching input hashes, configuration, boundary, grid and scientific pipeline code. pyWaPOR's thermal sharpening uses a `BaggingRegressor` without a fixed `random_state`; fresh runs can differ.

| Whole-month area-weighted output | Earlier run | v0.7 acceptance run |
| --- | ---: | ---: |
| ET (mm) | 84.4999289 | 84.4172569 |
| NPP (gC/m²) | 14.4872354 | 14.4656084 |
| Relative root-zone saturation | 0.456125993 | 0.455898520 |
| Reference ET (mm) | 239.429909 | 239.429909 |

ET differed by approximately 0.098% and NPP by 0.149%. These are recorded differences, not field-accuracy estimates or a new scientific acceptance tolerance. The UI integration did not change the model or add a random seed. Preserve each run rather than claiming pixel-identical reproducibility. References: [FAO thermal sharpener](https://www.fao.org/aquastat/py-wapor/pywapor_api_rsts/enhancers/dms/thermal_sharpener.html), [scikit-learn random-state behaviour](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.BaggingRegressor.html).

## Limits of this evidence

The tests establish execution, output integrity and arithmetic consistency. They do not validate ecological causality, satellite accuracy, local groundwater observations, crop yield or another team's historical assessment. This v0.7 baseline did not cover arbitrary-region water modelling or protection/OECM uploads. The v0.8 evidence above adds bounded online protection/OECM analysis; custom water remains pending. See [capability gaps](online-workflow-gaps.md).
