# Validation record — 14 September 2026

This records software behaviour. It is not ecological field validation, project acceptance or evidence of verified 2020–2021 land-cover change.

## Public-data comparison

Input data: ESA WorldCover 2020 v100 and 2021 v200, tile N18E084; gbOpen Ganjam pilot AOI. The 50 m EPSG:6933 target grid has 1,962 columns × 3,237 rows (6,350,994 cells/year).

The Python engine independently performs raster reprojection, masking, class statistics, transitions and SciPy-based fragmentation. The browser uses GeoTIFF.js, Proj4js and a separate typed-array implementation of connected components and exact Euclidean distances.

`pnpm run test:demo` verifies:

- Per-year class pixel counts agree exactly.
- Common valid coverage and changed pixel counts agree exactly.
- Gross gains, gross losses and net changes agree.
- All 91 checked numerical outputs agree within 1e-6.
- SHA-256 digests of the classification arrays agree for all 12,701,988 fragmentation cells across both years.

Input checksums, download URLs and the machine-readable result are in `public/data/worldcover/metadata.json` and `validation.json`. Regenerate using `engine/scripts/prepare_web_demo.py` and `pnpm run test:demo`.

## Known-answer tests

Python and TypeScript suites test a forest ring with independently known forest/core/edge/clearing areas and perimeter, all-forest administrative boundaries, NoData holes, eight-connected diagonal patches, protection stratification without artificial edges, majority patch ownership, LPI bounds and absent forest.

Frontend tests also compare Euclidean distances to brute-force distances; verify common-valid change accounting and crosswalk aggregation; round-trip GeoTIFF codes, CRS and NoData; import three synthetic GeoTIFFs and polygon/Shapefile fixtures; check protected/OECM overlap precedence; and reject invalid years, definitions and resolution.

Synthetic files under `tests/fixtures/` are explicitly marked test-only and are not served as study results.

## Interactive browser checks

- Run both modules on the real two-period Ganjam inputs and inspect the computed maps, matrix, gains/losses and forest metrics.
- Switch among land cover, forest fragmentation and class difference layers.
- Download and reopen the forest GeoTIFF: CRS EPSG:6933, 50 m cells, NoData 255 and every classification pixel matches Python.
- Download and read the transition CSV: its cells sum to 840,703.25 ha, matching the common valid footprint.
- Download and inspect the JSON manifest: input hashes, parameters, coverage and area-conservation checks are present.
- Upload three GeoTIFF periods, a GeoJSON AOI, a zipped protected-area Shapefile and overlapping OECM GeoJSON; obtain two comparison periods and four forest strata.
- Import a custom CSV crosswalk and verify the forest selector reflects the merged class.
- Reject an edge width smaller than one analysis cell with an actionable message.

## Limits

WorldCover release algorithms differ. The demonstration is conditional on resampling, source class quality, forest definition and AOI boundary assumptions. No real protected-area or OECM evidence is included in the public example. Field validation, historical protection status, accepted project inputs and suitability/priority rules remain outside this software test.
