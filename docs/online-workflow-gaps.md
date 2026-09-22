# Online workflow: supported scope and remaining work

Status checked against the v0.7 implementation on 22 September 2026. This is a capability inventory, not a claim that every retained advanced feature is available online. The eight-module workspace and the optional Python GIS engine serve different workflows.

## Available now

- One browser submission flow, shared study area, persistent task history, cancellation and retained partial results for seven environmental diagnostics plus the Fayoum water pilot.
- Recalculation of all seven Ganjam reference modules, including GLC-FCS30D 2002/2012/2022, and bounded source acquisition for new-area environmental tasks.
- New-area climate periods, models, scenarios, thresholds; groundwater periods; VHI seasons and reference years; flood return periods; land-cover grid size and forest-edge options.
- GeoTIFF, CSV, result ZIP and run manifests with sources, methods, hashes and missing-data rules. Browser sessions require no shared access code or local Python installation.
- Separate standalone GIS/CLI and browser analysis implementations, including advanced categorical features retained in source.

## Priorities for completing the online migration

| Priority | Capability | Current evidence | Remaining work / acceptance evidence |
| --- | --- | --- | --- |
| 1 | Flexible land-cover inputs and years | `AnalysisWizard.tsx` accepts GeoJSON/rectangles; `diagnostics/models.py` exposes grid/edge/mangrove options only. Ganjam is a fixed reference; new regions use WorldCover 2020/2021. | Add bounded GeoTIFF and zipped Shapefile uploads, 1–3 forest or 2–3 change periods, source selection and validation inside the online flow. Test one custom three-period analysis through submission and downloads. |
| 1 | Editable crosswalk and forest definition | `LandCoverLab.tsx` and `analysis/runner.ts` retain CSV crosswalks and forest classes; online requests do not carry them. | Carry validated class mappings, names, colours, NoData rules and forest selections into server jobs and manifests. Preserve defaults without silently treating them as project-approved definitions. |
| 1 | Protected/OECM/remainder statistics | Both numerical engines support strata; the online worker calls `classify_forest` without strata and explicitly reports coverage as unassessed. | Acquire or accept appropriate polygon layers; keep versions/dates and completeness. Classify the whole AOI before stratifying. Verify overlaps, boundary effects, area conservation and whole-patch allocation. Points alone cannot define protected-area boundaries. |
| 1 | Change matrix, gains/losses and forest comparison charts | Online exports contain transition rows and whole-area forest metrics. `Results.tsx` retains the advanced matrix and gains/losses chart; these are not used by `DiagnosticResults.tsx`. | Render the matrix, gross gain/loss/net summaries, multi-period map comparisons and forest area/change charts from server outputs. Verify common-coverage denominators and row/column totals. |
| 2 | Complete forest reporting table | Online metrics include PLAND, NP, TE, ED, MPE, MSI, AWMSI, MPS, LPI, class areas and clearing counts. | Add explicit patch/edge shares, perforation ratio, edge per forest hectare and largest-patch share of forest; document each denominator and units. Add period/stratum comparisons after strata are available. These are different quantities from LPI. |
| 2 | Shareable maps and diagnostic brief | The advanced tools retain PNG and brief exporters; online buttons expose GeoTIFF, tables, manifest and ZIP. | Add report-ready map images and a unified eight-module brief with source dates, scales, coverage, missing modules and field-check questions. A screenshot does not replace numerical exports. |
| 2 | Custom-region water modelling | `custom_ready` requires provider configuration; current verified run uses Fayoum, July 2021. | Configure remaining providers, acquire actual data for a small new AOI, verify resource use and numerical outputs, then enable the option. Do not combine a Ganjam analysis with a different-region sample. |
| 2 | Original-assessment comparison | Current evidence checks Python/browser agreement, arithmetic, conservation and deployed workflows. | Compare against an independently supplied frozen AOI, source rasters, classification and reference outputs. Record differences in grid, edge/perimeter algorithms, time periods and aggregation. Existing tests are not proof of matching another assessment. |
| 3 | Sankey diagram | No implementation found in the retained or online result components. | Optional visualisation from the validated transition matrix. Keep source class totals and missing coverage explicit. |

## Interpretation details to preserve

- Native 0.25° groundwater and climate cells remain coarse. Regional groundwater storage is not well depth; resampling does not add village-scale information.
- WorldCover releases use different map algorithms. Source differences are not automatically real land-cover changes. The Ganjam GLC-FCS30D source is 30 m, while the prepared reference grid is 50 m.
- Internal clearings are non-forest, not a fourth part of forest area. Patch/edge/core sum to forest; NP counts connected forest components, not only the red map category. LPI divides by landscape area, while a largest-patch forest share uses forest area.
- Preserve product-specific source periods and eligible-area denominators. MODIS VHI is not ASIS; NPP is not crop yield. The low-emission scenario and the published degradation period discrepancy remain separate questions.
- The current water thermal sharpener is stochastic; retain result manifests and actual outputs. See [repeatability evidence](online-validation.md).
- Sessions are browser-specific and outputs expire after 30 days. Cross-device retrieval, durable project archives and collaborator sharing need an explicit product design; removing the access-code form does not create a user account system.

## Separate extensions

Additional hazards, suitability/priority scoring, intervention selection, yield-gap assessment, external project integrations and a QGIS plugin are not implemented by the current eight-module workflow. These extensions need their own thresholds, methods and acceptance criteria. Water/NPP outputs alone do not complete an irrigation performance or yield-gap assessment.

The intended next release should migrate the retained categorical controls and result presentation into the current workflow while keeping its single entry. The temporary hiding of advanced tools should not be mistaken for completion of that migration.
