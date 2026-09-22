from fastapi.testclient import TestClient
import time
import pytest
from online.api import create_app
from online.analyses import Analyses, AnalysisRequest
from online.config import Settings
from online.models import rectangle, SAMPLE_BBOX
from test_diagnostics import custom

AUTH={'Authorization':'Bearer '+'a'*40,'Idempotency-Key':'eight-module-submit-001'}
OTHER={'Authorization':'Bearer '+'b'*40}

@pytest.fixture
def service(tmp_path):
    settings=Settings(data=tmp_path,keys={'alice':'a'*40,'bob':'b'*40},min_free_bytes=0)
    app=create_app(settings)
    (tmp_path/'sample').mkdir()
    (tmp_path/'sample/ready.json').write_text('{}')
    (tmp_path/'diagnostics/sample-ready.json').write_text('{}')
    return TestClient(app),app.state.analyses,settings

def combined():
    diagnostic=custom(['degradation']);diagnostic['boundary']=rectangle(SAMPLE_BBOX)
    return {'name':'Fayoum combined','diagnostics':diagnostic,'water':{}}

def test_group_idempotency_private_history_and_cancel(service):
    c,g,_=service
    assert c.get('/api/analyses').status_code==401
    response=c.post('/api/analyses',json=combined(),headers=AUTH)
    assert response.status_code==202,response.text
    a=response.json();key=a['id']
    assert a['modules']==['degradation','water'] and len(a['children'])==2
    assert {v['job']['request']['name'] for v in a['children']}=={'Fayoum combined'}
    assert c.post('/api/analyses',json=combined(),headers=AUTH).json()['id']==key
    assert len(c.get('/api/analyses',headers=AUTH).json())==1
    assert c.get('/api/analyses',headers=OTHER).json()==[]
    assert c.post('/api/analyses/'+key+'/cancel',headers=OTHER).status_code==404
    changed=combined();changed['name']='Different'
    assert c.post('/api/analyses',json=changed,headers=AUTH).status_code==409
    cancelled=c.post('/api/analyses/'+key+'/cancel',headers=AUTH).json()
    assert cancelled['status']=='cancelled'
    assert all(v['job']['status']=='cancelled' for v in cancelled['children'])

def test_preflight_rejects_mismatched_regions_and_unavailable_water(service):
    c,g,_=service
    wrong=combined();wrong['diagnostics']=custom(['flood'])
    assert c.post('/api/analyses',json=wrong,headers=AUTH).status_code==422
    wrong=combined();wrong['diagnostics']={'mode':'ganjam','modules':['flood']}
    assert c.post('/api/analyses',json=wrong,headers=AUTH).status_code==422
    wrong=combined();wrong['water']={'mode':'custom'}
    assert c.post('/api/analyses',json=wrong,headers=AUTH).status_code==503
    assert c.post('/api/analyses',json={'name':'Empty'},headers=AUTH).status_code==422
    assert g.list('alice')==[]
    assert all(q.list('alice')==[] for q in g.queues.values())

def test_durable_intent_recovers_between_child_creation(service,monkeypatch):
    _,g,settings=service
    body=AnalysisRequest.model_validate(combined()).model_dump(mode='json')
    def crash(*args,**kwargs):raise RuntimeError('simulated process exit')
    monkeypatch.setattr(g.queues['water'],'create',crash)
    with pytest.raises(RuntimeError):g.create('alice','crash-recovery-001',body)
    assert len(g.queues['diagnostics'].list('alice'))==1
    assert g.queues['water'].list('alice')==[]
    recovered=Analyses(settings);recovered.dispatch();recovered.dispatch()
    assert len(recovered.queues['diagnostics'].list('alice'))==1
    assert len(recovered.queues['water'].list('alice'))==1
    assert len(recovered.list('alice'))==1
    assert recovered.create('alice','crash-recovery-001',body)['id']==recovered.list('alice')[0]['id']

def test_queue_full_waits_and_cancel_prevents_missing_child_creation(service):
    c,g,s=service;water=g.queues['water']
    for i in range(2):water.create('alice',f'existing-water-{i}',{'name':'Existing','mode':'sample'},s)
    a=c.post('/api/analyses',json=combined(),headers=AUTH).json()
    assert next(v for v in a['children'] if v['kind']=='water')['job'] is None
    assert a['status']=='queued'
    c.post('/api/analyses/'+a['id']+'/cancel',headers=AUTH)
    for job in water.list('alice'):water.cancel(job['id'],'alice')
    Analyses(s).dispatch()
    assert len(water.list('alice'))==2
    assert next(v for v in g.list('alice') if v['id']==a['id'])['status']=='cancelled'

def test_partial_results_and_legacy_history(service):
    c,g,s=service;a=c.post('/api/analyses',json=combined(),headers=AUTH).json()
    for child in a['children']:g.queues[child['kind']].finish(child['job']['id'],'succeeded' if child['kind']=='diagnostics' else 'failed')
    assert c.get('/api/analyses',headers=AUTH).json()[0]['status']=='partial'
    old=g.queues['water'].create('alice','previous-water-task',{'name':'Old water task'},s)
    listing=c.get('/api/analyses',headers=AUTH).json()
    assert len(listing)==2 and next(r for r in listing if r['legacy'])['id']=='water:'+old['id']
    assert c.post('/api/analyses/water:'+old['id']+'/cancel',headers=AUTH).json()['status']=='cancelled'

def test_group_quota_and_shared_custom_boundary(service):
    c,_,_=service
    for i in range(3):
        r=c.post('/api/analyses',json={'name':'Ganjam','diagnostics':{'modules':['flood']}},headers={**AUTH,'Idempotency-Key':f'quota-group-{i:08d}'})
        assert r.status_code==(202 if i<2 else 429)
    req=combined();req['water']={'mode':'custom'}
    parsed=AnalysisRequest.model_validate(req)
    assert parsed.water.boundary==parsed.diagnostics.boundary

def test_background_dispatch_survives_without_browser_polling(service):
    client,g,s=service
    for i in range(2):
        g.queues['water'].create('alice',f'occupied-slot-{i}',{'name':'Existing'},s)
    with client:
        a=client.post('/api/analyses',json=combined(),headers=AUTH).json()
        assert a['children'][1]['job'] is None
        for old in g.queues['water'].list('alice'):
            g.queues['water'].cancel(old['id'],'alice')
        child_id=g.child_id(a['id'],'water')
        deadline=time.monotonic()+6
        while g.queues['water'].get(child_id) is None and time.monotonic()<deadline:
            time.sleep(.05)
        assert g.queues['water'].get(child_id)['status']=='queued'
