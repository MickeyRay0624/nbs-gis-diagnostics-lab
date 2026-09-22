import json
import time
import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from pyproj import Transformer
from fastapi.testclient import TestClient
from online.api import create_app
from online.config import Settings
from online.models import rectangle
from diagnostics.models import DiagnosticRequest
from diagnostics.uploads import vector_document
from diagnostics.land import transition_rows, forest_changes, derived, reclassify, run_land
from diagnostics.results import Publisher
from nbs_gis.fragmentation import classify_forest
from test_diagnostics import custom, AUTH, OTHER


def tif(a, transform=None, nodata=0):
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=a.shape[1],height=a.shape[0],count=1,dtype=a.dtype,crs='EPSG:6933',transform=transform or from_origin(8200000,2500000,50,50),nodata=nodata) as dst:dst.write(a,1)
        return mem.read()


def put(c,body,kind='raster',name='map.tif',headers=AUTH):
    return c.post('/api/diagnostics/uploads',params={'kind':kind,'name':name},headers={**headers,'Content-Type':'application/octet-stream'},content=body)


@pytest.fixture
def service(tmp_path):
    app=create_app(Settings(data=tmp_path,keys={'alice':'a'*40,'bob':'b'*40},min_free_bytes=0))
    (tmp_path/'diagnostics/sample-ready.json').write_text('{}')
    return TestClient(app),app,tmp_path


def test_upload_ownership_and_content_inspection(service):
    c,app,_=service
    assert put(c,b'not a TIFF').status_code==422
    assert put(c,b'{}','vector','area.geojson').status_code==422
    assert put(c,b'[]','vector','area.geojson').status_code==422
    assert put(c,tif(np.ones((3,3),dtype='uint8')),headers={}).status_code==401
    assert put(c,tif(np.full((3,3),1.5,dtype='float32'))).status_code==422
    a=np.array([[0,1,2],[2,65534,65535]],dtype='uint16')
    response=put(c,tif(a,nodata=65535));assert response.status_code==201,response.text
    upload=response.json();assert upload['info']['codes']==[1,2,65534] and 'owner' not in upload
    assert app.state.uploads.path(upload['id']).stat().st_mode&0o777==0o600
    req={'modules':['fragmentation'],'land_cover':{'source':'uploaded','rasters':[{'year':2022,'upload_id':upload['id']}],
        'crosswalk':[{'source':v,'code':i+1,'name':str(v),'color':'#338844'} for i,v in enumerate([1,2,65534])],'forest_codes':[1]}}
    assert c.post('/api/diagnostics/jobs',json=req,headers={**OTHER,'Idempotency-Key':'other-owner-00001'}).status_code==422
    missing=json.loads(json.dumps(req));missing['land_cover']['crosswalk'].pop()
    assert c.post('/api/diagnostics/jobs',json=missing,headers=AUTH).status_code==422
    assert c.post('/api/diagnostics/jobs',json=req,headers=AUTH).status_code==202
    c.post(f"/api/diagnostics/uploads/{upload['id']}/discard",headers=AUTH)
    assert app.state.uploads.path(upload['id']).exists()
    app.state.uploads.path(upload['id']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum'):app.state.uploads.verified(upload['id'])


def test_stream_limit_reservation_expiry_and_vector_geometry(service,monkeypatch):
    import diagnostics.uploads as u
    c,app,_=service;monkeypatch.setattr(u,'MAX_RASTER',100)
    assert put(c,b'x'*101).status_code==413
    with app.state.uploads.connect() as db:assert db.execute('SELECT count(*) FROM uploads').fetchone()[0]==0
    with pytest.raises(ValueError):vector_document({'type':'FeatureCollection','features':[{'geometry':{'type':'Point','coordinates':[0,0]}}]})
    response=put(c,json.dumps(rectangle([85,20,85.1,20.1])).encode(),'vector','protected.geojson')
    assert response.status_code==201,response.text
    key=response.json()['id']
    with app.state.uploads.connect() as db:db.execute('UPDATE uploads SET expires=? WHERE id=?',(time.time()-1,key))
    app.state.uploads.cleanup();assert not app.state.uploads.path(key).exists()


def test_change_uses_common_valid_cells_and_high_target_codes():
    a=np.array([[1,1,999],[1,999,0]],dtype='uint16');b=np.array([[1,999,1],[0,999,1]],dtype='uint16')
    tr,rows=transition_rows(a,b,[(1,'A','#ffffff'),(999,'B','#000000')],2000,2020,.25)
    assert len(tr)==4 and sum(r['area_ha'] for r in tr)==1
    assert all(r['common_valid_ha']==1 for r in rows)
    assert [(r['gross_gain_ha'],r['gross_loss_ha'],r['net_ha']) for r in rows]==[(.25,.25,0),(.25,.25,0)]
    assert reclassify(np.array([[65534,0]],dtype='uint16'),[dict(source=65534,code=999)]).tolist()==[[999,0]]
    assert reclassify(np.array([[10,1]],dtype='uint16'),[dict(source=10,code=0),dict(source=1,code=999)]).tolist()==[[0,999]]
    with pytest.raises(ValueError,match='Crosswalk'):reclassify(a,[dict(source=1,code=1)])


def test_forest_strata_do_not_create_edges_and_derived_units():
    source=np.ones((12,12),dtype='uint16');source[2:10,2:10]=2;source[5,5]=1
    strata=np.full(source.shape,3,dtype='uint8');strata[:,:6]=1;strata[:,6:9]=2
    all_out,_,_=classify_forest(source,[2],50,50)
    out,rows,qa=classify_forest(source,[2],50,50,strata=strata)
    assert np.array_equal(out,all_out) and qa['class_conservation'] and qa['straddling_patches']==1
    metrics=[derived(r) for r in rows]
    assert sum(r['forest_ha'] for r in metrics[1:])==metrics[0]['forest_ha']
    assert sum(r['TE_km'] for r in metrics[1:])==pytest.approx(metrics[0]['TE_km'])
    assert metrics[0]['TE_km']==metrics[0]['TE_m']/1000
    assert metrics[0]['patch_pct']+metrics[0]['edge_pct']+metrics[0]['core_pct']==pytest.approx(100)
    assert metrics[0]['perforation_pct']==pytest.approx(metrics[0]['clearing_ha']/metrics[0]['forest_ha']*100)
    altered=out.copy();altered[:,0:2]=255
    assert all(r['net_ha']==0 for r in forest_changes(out,altered,2000,2020,.25,strata))
    noforest=derived(classify_forest(np.ones((3,3),dtype='uint16'),[2],50,50)[1][0])
    assert noforest['core_pct'] is None and noforest['MPS_ha'] is None


def test_three_period_upload_pipeline_records_definition_and_exports(service,tmp_path):
    c,app,root=service;transform=from_origin(8200000,2500000,50,50)
    to_geo=Transformer.from_crs(6933,4326,always_xy=True)
    west,south=to_geo.transform(8200000,2499000);east,north=to_geo.transform(8201000,2500000)
    boundary=rectangle([west,south,east,north]);refs=[]
    for i,year in enumerate([2002,2012,2022]):
        a=np.ones((20,20),dtype='uint16');a[2:18,2:18]=65534;a[5+i:8+i,5:8]=1;a[0,i]=0
        response=put(c,tif(a,transform),name=f'land-{year}.tif');assert response.status_code==201,response.text
        refs.append(dict(year=year,upload_id=response.json()['id']))
    response=put(c,json.dumps(rectangle([west,south,(west+east)/2,north])).encode(),'vector','pa.geojson');assert response.status_code==201
    req=custom(['lulc','fragmentation']);req['boundary']=boundary
    req['land_cover']={'source':'uploaded','source_name':'QA synthetic maps','rasters':refs,'protected_upload_id':response.json()['id'],
        'crosswalk':[dict(source=1,code=1,name='=Crop label',color='#ddbb33'),dict(source=65534,code=999,name='Forest',color='#228844')],'forest_codes':[999]}
    parent=c.post('/api/analyses',json={'name':'Three periods','diagnostics':req},headers=AUTH)
    assert parent.status_code==202,parent.text
    job=parent.json()['children'][0]['job'];folder=root/'diagnostics/jobs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    publisher=Publisher(folder,job['request'],boundary,'Synthetic acceptance fixture; not field observations.')
    run_land(publisher,job['request'],tmp_path)
    result=publisher.finish();assert result['complete'] and len(result['layers'])==9
    assert result['land']['years']==[2002,2012,2022] and len(result['land']['inputs'])==4
    metrics=next(t['rows'] for t in result['tables'] if t['file']=='forest-metrics.csv');assert len(metrics)==12
    assert all(r['forest_ha']==0 for r in metrics if r['stratum']=='OECM')
    for y in [2002,2012,2022]:
        group=[r for r in metrics if r['year']==y];assert sum(r['forest_ha'] for r in group[1:])==group[0]['forest_ha']
    assert "'=Crop label" in (publisher.out/'class-crosswalk.csv').read_text()
    assert (publisher.out/'input-manifest.json').exists() and (publisher.out/'protected.geojson').exists()


def test_land_period_selection_and_definition_validation():
    assert DiagnosticRequest.model_validate({'modules':['fragmentation'],'land_cover':{'years':[2012]}}).land_cover.years==[2012]
    for land in [{'years':[2012]},{'years':[2002,2002]},{'years':[2000,2012]},{'resolution':30}]:
        with pytest.raises(ValueError):DiagnosticRequest.model_validate({'modules':['lulc'],'land_cover':land})
    with pytest.raises(ValueError):DiagnosticRequest.model_validate({'modules':['fragmentation'],'land_cover':{'crosswalk':[dict(source=1,code=1,name='Trees',color='#00aa00')]}})
