# Online workflow: supported scope and remaining work

Status checked against the v0.8 implementation on 22 September 2026. This is a capability inventory, not a claim that every retained advanced feature is available online. The eight-module workspace and the optional Python GIS engine serve different workflows.

## Available now

- One browser submission flow, shared study area, persistent task history, cancellation and retained partial results for seven environmental diagnostics plus the Fayoum water pilot.
- Recalculation of all seven Ganjam reference modules, including GLC-FCS30D 2002/2012/2022, and bounded source acquisition for new-area environmental tasks.
- New-area climate periods, models, scenarios, thresholds; groundwater periods; VHI seasons and reference years; flood return periods; land-cover grid size and forest-edge options.
- GeoTIFF, CSV, result ZIP and run manifests with sources, methods, hashes and missing-data rules. Browser sessions require no shared access code or local Python installation.
- Separate standalone GIS/CLI and browser analysis implementations, including advanced categorical features retained in source.

## Migration status in v0.8

The online workflow now carries bounded GeoTIFF sources and years, crosswalk CSVs, forest selections and protected/OECM polygon layers into private server jobs. The server produces complete transition matrices, gross gain/loss/net tables, common-coverage forest changes, stratum metrics and the missing derived ratios. Results render charts, period-map comparisons and PNG exports; the unified HTML/Markdown brief records every module status.

See [method differences and comparison checklist](method-differences.md). CDSE activation and NASA LAADS profile/authorization are complete; real Sentinel-2, VIIRS geolocation, ERA5 and AgERA5 download probes pass. A fresh acquisition/model/export run remains the dependency for enabling new water regions. Original-assessment validation still requires independently supplied files listed in [the intake manifest](reference-comparison-files.csv). Optional Sankey diagrams, cross-device accounts/sharing and permanent archives remain separate future work.

## Interpretation details to preserve

- Native 0.25° groundwater and climate cells remain coarse. Regional groundwater storage is not well depth; resampling does not add village-scale information.
- WorldCover releases use different map algorithms. Source differences are not automatically real land-cover changes. The Ganjam GLC-FCS30D source is 30 m, while the prepared reference grid is 50 m.
- Internal clearings are non-forest, not a fourth part of forest area. Patch/edge/core sum to forest; NP counts connected forest components, not only the red map category. LPI divides by landscape area, while a largest-patch forest share uses forest area.
- Preserve product-specific source periods and eligible-area denominators. MODIS VHI is not ASIS; NPP is not crop yield. The low-emission scenario and the published degradation period discrepancy remain separate questions.
- The current water thermal sharpener is stochastic; retain result manifests and actual outputs. See [repeatability evidence](online-validation.md).
- Sessions are browser-specific and outputs expire after 30 days. Cross-device retrieval, durable project archives and collaborator sharing need an explicit product design; removing the access-code form does not create a user account system.

## Separate extensions

Additional hazards, suitability/priority scoring, intervention selection, yield-gap assessment, external project integrations and a QGIS plugin are not implemented by the current eight-module workflow. These extensions need their own thresholds, methods and acceptance criteria. Water/NPP outputs alone do not complete an irrigation performance or yield-gap assessment.

The retained advanced-tools entry remains hidden. Its local-only workflow is separate from the uploaded-input server workflow.
