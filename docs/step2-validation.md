# Step 2 validation evidence

The first release separates numerical correctness, input quality and expert acceptance. The following evidence is reproducible from the checked-in prepared data unless raw Earth Engine inputs are explicitly required.

| Check | Evidence | Scope |
| --- | --- | --- |
| TypeScript analytical tests | `pnpm test`: 20 tests | Known forest geometry, common footprints, NoData, negative/zero values, CSV/GeoTIFF round trips, malformed catalog rejection and checksum enforcement |
| Python analytical tests | `pytest engine/tests`: 20 tests | Existing GIS engine plus VHI reference ranges, dry spells/threshold units, SOC rounding and incomplete components |
| GLC-FCS30D cross-language run | `public/data/glcfcs/validation.json` | Every forest class pixel across three 6,350,994-cell grids; class counts, all three transitions and forest metrics |
| Numeric packages | `public/data/step2/validation.json` | 575 numeric/area checks; 97 output layers across groundwater, drought, climate, flood and degradation |
| Climate daily aggregation | `public/data/step2/climate-daily-validation.json` | Six indices for ACCESS-CM2 in 1991 and leap year 1992; requires ignored daily source exports to rebuild |
| Degradation provider comparison | `public/data/step2/degradation-provider-validation.json` | Local combination matches published baseline/latest indicator on complete, unambiguous source cells |

Climate count indices and missingness match the independent daily aggregation. Temperature allows 0.00005°C for Float32 rounding at different processing stages; this is not a model-uncertainty estimate. The original four baseline disagreements in the degradation check occurred at integer SOC −10%; those threshold-boundary values are now explicitly uncertain, not tuned to force a classification.

Browser checks cover actual Ganjam runs, module/layer changes, persistent map context, opacity, numerical outputs and downloads. The application reports all seven modules as prepared, and expert review as pending. The map stays mounted; running analysis does not navigate to another page.

Remaining review items: local forest definition, cropping calendar and monsoon observation availability; climate model/threshold relevance and the absence of a low-emission scenario; published LC/SOC date discrepancy and the carbon model; protected-area/OECM completeness; and confirmation of mapped patterns against local observations. No result is claimed to be an official SDG submission or a field-verified diagnosis.
