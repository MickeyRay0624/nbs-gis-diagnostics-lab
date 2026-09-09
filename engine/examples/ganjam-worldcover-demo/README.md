# Ganjam WorldCover technical demonstration

This example runs the complete NbS LULC command-line workflow with a real district boundary and real public land-cover rasters. It is intended to demonstrate the software, not to produce an NbS project finding.

## Demonstration data

- AOI: the current Ganjam District boundary used by the browser prototype.
- LULC: ESA WorldCover 2020 v100 and 2021 v200, tile `N18E084`, downloaded from the public ESA WorldCover AWS bucket.
- Live-demo grid: 100 m in EPSG:6933 so the run completes quickly. Change `target_resolution` to 30 for a higher-resolution technical run.

WorldCover 2020 and 2021 were produced with different algorithm versions. Apparent differences can therefore reflect both actual land-cover change and methodology changes. Do not interpret the resulting change statistics as project evidence.

## Run the demonstration

From the repository root, with the engine environment active:

```bash
bash engine/examples/ganjam-worldcover-demo/download_data.sh
nbs-gis preflight --config engine/examples/ganjam-worldcover-demo/config.yml
nbs-gis run-lulc --config engine/examples/ganjam-worldcover-demo/config.yml
```

The command prints the timestamped result directory under `engine/outputs/worldcover-demo/`. Existing run directories are never overwritten.

## Source and attribution

- Data access: https://esa-worldcover.org/en/data-access
- 2020 dataset: https://doi.org/10.5281/zenodo.5571936
- 2021 dataset: https://doi.org/10.5281/zenodo.7254221

Required map attribution: `© ESA WorldCover project 2020/2021 / Contains modified Copernicus Sentinel data processed by ESA WorldCover consortium.`
