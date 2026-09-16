"""Compare EE yearly outputs against independent daily NumPy calculations."""

import calendar
import hashlib
import json
import numpy as np
import rasterio
from prepare_step2_climate import annual_indices, METRICS
from step2_package import CACHE, OUT

checks = []
for year in [1991, 1992]:
    blocks = []
    hashes = {}
    for month in [1, 7]:
        path = CACHE / f"climate-daily-{year}_{month}.tif"
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with rasterio.open(path) as s:
            d = s.read().astype("float64")
            d[d == -9999] = np.nan
            blocks.append(d.reshape(-1, 4, *s.shape))
    raw = np.concatenate(blocks)
    assert len(raw) == 365 + calendar.isleap(year)
    expected = annual_indices(raw)
    with rasterio.open(CACHE / "climate_access-cm2_ssp245_1991.tif") as s:
        observed = s.read(list(range((year - 1991) * 6 + 1, (year - 1991) * 6 + 7)))
        observed[observed == -9999] = np.nan
    assert np.array_equal(np.isnan(observed), np.isnan(expected))
    for i, (key, _, _) in enumerate(METRICS):
        error = float(np.nanmax(np.abs(observed[i] - expected[i])))
        # Daily and yearly exports round at different stages to Float32; at
        # ~300 K, one Float32 ULP is about 3e-5 K. Counts must still be exact.
        tolerance = 5e-5 if key == "temperature" else 1e-6
        assert error <= tolerance, (year, key, error)
        checks.append(
            dict(
                year=year,
                metric=key,
                maxAbsoluteError=error,
                tolerance=tolerance,
                validPixels=int(np.isfinite(expected[i]).sum()),
            )
        )
report = dict(
    status="pass",
    method="Independent NumPy aggregation from daily ACCESS-CM2 historical values; normal and leap years",
    checks=checks,
    limitation="Checks annual aggregation, not climate-model skill or all model/scenario outputs.",
)
(OUT / "climate-daily-validation.json").write_text(json.dumps(report, indent=2) + "\n")
print("PASS: all six indices agree for normal and leap years (12 checks).")
