"""Run in the diagnostics image; fixtures exercise real export and missing-data handling."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from nbs_prepare.core import NoValidDataError, area_weights, grid_for, identity
from diagnostics.pipeline import run
from online.worker import public_source_error


def request(modules):
    return dict(mode="custom", name="Missing observations regression", modules=modules,
        boundary={"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[85.15,20.43],[85.16,20.43],[85.16,20.44],[85.15,20.44],[85.15,20.43]]]}}]},
        config=dict(schema="nbs-local-job/v1", name="Missing observations regression", modules=modules, boundarySha256="0"*64,
            groundwater=dict(baseline=[2003,2013],monitoring=[2014,2023]),
            drought=dict(reference=[2001,2023],minimumYears=15,compare=[2013,2023],seasons=[dict(name="Growing season",start=6,end=10)]),
            climate=dict(baseline=[1991,2020],future=[2041,2070],models=["ACCESS-CM2"],scenarios=["ssp245"],metrics=["hot"],thresholds=dict(hot=35,warm=25,rain=20,dry=1)),
            flood=dict(returnPeriods=[10]),landMask="all-land",maxDownloadGB=10))


def prepared(module, value):
    def runner(ctx):
        transform, shape = grid_for(ctx.aoi,1/1200)
        spec=identity(module+"-fixture",1,"Synthetic observation","m","Test fixture")
        ctx.write(module,[np.full(shape,value,dtype="float32")],["Synthetic observation"],transform,4326,
            area_weights(ctx.aoi,ctx.area_aoi,transform,shape),
            dict(id=module+"-source",name="Synthetic test input",url="https://example.invalid/fixture",version="test",licence="test",description="Test only",resolution="3 arc seconds"),
            [spec],["Synthetic test only"],["Not environmental evidence"])
    return runner


class MissingObservationsTests(unittest.TestCase):
    def execute(self, folder, modules, flood):
        (folder/"request.json").write_text(json.dumps(request(modules)))
        with patch.dict("diagnostics.pipeline.RUNNERS",{"flood":flood,"degradation":prepared("degradation",2.0)}),contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
            run(folder)
        return json.loads((folder/"results/result.json").read_text())

    def test_empty_source_preserves_completed_module_and_reports_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            result=self.execute(folder,["flood","degradation"],prepared("flood",np.nan))
            self.assertFalse(result["complete"])
            flood=next(m for m in result["modules"] if m["id"]=="flood")
            self.assertEqual(flood["reason_code"],"no_valid_observations")
            self.assertIn("RP10",flood["missing"][0])
            self.assertIn("not an account",flood["missing"][0])
            self.assertEqual(result["validation"]["completed_modules"],["degradation"])
            self.assertTrue(all(l["module"]=="degradation" for l in result["layers"]))
            self.assertTrue(all(l["stats"]["mean"]==2 for l in result["layers"]))

    def test_only_empty_source_has_specific_public_error_and_no_fake_map(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with self.assertRaisesRegex(RuntimeError,"No diagnostic completed"):
                self.execute(folder,["flood"],prepared("flood",np.nan))
            self.assertEqual(json.loads((folder/"source-error.json").read_text())["code"],"no_valid_flood_observations")
            self.assertIn("does not establish zero flood risk",public_source_error(folder))
            self.assertFalse((folder/"results/result.json").exists())

    def test_observed_zero_values_are_distinct_from_missing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            result=self.execute(Path(directory),["flood"],prepared("flood",0.0))
            self.assertTrue(result["complete"])
            self.assertEqual(result["layers"][0]["stats"]["mean"],0)
            self.assertGreater(result["layers"][0]["stats"]["validAreaKm2"],0)

    def test_unclassified_errors_do_not_expose_provider_details(self):
        def failed(ctx):raise RuntimeError("private-token-and-signed-url")
        with tempfile.TemporaryDirectory() as directory:
            result=self.execute(Path(directory),["flood","degradation"],failed)
            flood=next(m for m in result["modules"] if m["id"]=="flood")
            self.assertNotIn("reason_code",flood)
            self.assertNotIn("private-token",json.dumps(result))


if __name__=="__main__":unittest.main()
