"""Run with the model environment: tests missing days, AOI holes and units."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
import rasterio
import rioxarray  # noqa: F401
import xarray as xr

from online.results import export_results


class ResultSemantics(unittest.TestCase):
    def test_missing_day_never_becomes_a_complete_total(self):
        with tempfile.TemporaryDirectory() as temp:
            model, out = Path(temp) / "model", Path(temp) / "out"
            model.mkdir()
            shape = (3, 2, 2)
            e, t, interception = np.ones(shape), np.full(shape, 2.), np.full(shape, .2)
            e[0, 0, 0] = np.nan
            values = {"e_24_mm": e, "t_24_mm": t, "int_mm": interception,
                      "aeti_24_mm": e + t + interception, "et_ref_24_mm": np.full(shape, 5.),
                      "se_root": np.full(shape, .4), "npp": np.full(shape, .5)}
            ds = xr.Dataset({k: (("time_bins", "y", "x"), v) for k, v in values.items()},
                            coords={"time_bins": pd.date_range("2021-01-31", periods=3), "y": [29.075, 29.025], "x": [31.025, 31.075]}).rio.write_crs(4326)
            ds.to_netcdf(model / "et_look_out.nc")
            (model / "configuration.json").write_text("{}")
            # Exclude the south-east pixel using a polygon hole.
            boundary = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [
                [[31,29],[31.1,29],[31.1,29.1],[31,29.1],[31,29]],
                [[31.06,29.01],[31.06,29.04],[31.09,29.04],[31.09,29.01],[31.06,29.01]],
            ]}}]}
            request = {"mode": "custom", "name": "Semantics test", "bbox": [31,29,31.1,29.1], "boundary": boundary,
                       "start": "2021-01-31", "end": "2021-02-02"}
            export_results(model, out, request, {"version": "test"})
            manifest = json.loads((out / "result.json").read_text())
            with rasterio.open(out / "whole.tif") as src:
                et = src.read(3, masked=True).filled(np.nan)
                self.assertTrue(np.isnan(et[0, 0]), "One missing daily value must invalidate the period total.")
                self.assertEqual(et[0, 1], 9.)
                self.assertTrue(np.isnan(et[1, 1]), "The AOI hole must stay excluded.")
                self.assertEqual(src.read(9)[1, 1], 0.)
                self.assertAlmostEqual(src.read(7)[0, 1], .4, places=6)
                self.assertEqual(src.read(8)[0, 1], 1.5)
            periods = {p["id"]: p for p in manifest["periods"]}
            self.assertEqual(periods["month-2021-01"]["days"], 1)
            self.assertEqual(periods["month-2021-02"]["days"], 2)
            self.assertIn("selected days", periods["month-2021-01"]["label"])
            layer = next(l for l in manifest["layers"] if l["id"] == "whole-et_24_mm")
            self.assertEqual(layer["stats"]["cells"], 2)
            self.assertGreater(layer["stats"]["coveragePct"], 66.)
            self.assertLess(layer["stats"]["coveragePct"], 67.)
            with xr.open_dataset(out / "daily-results.nc") as daily:
                self.assertTrue(np.isnan(daily.et_24_mm.values[0,0,0]))
                self.assertTrue(np.isnan(daily.et_24_mm.values[:,1,1]).all())


if __name__ == "__main__":
    unittest.main()
