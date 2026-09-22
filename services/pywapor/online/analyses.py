"""Durable analysis groups joining the two independently pinned compute queues."""
import asyncio
from contextlib import asynccontextmanager, contextmanager, suppress
from dataclasses import replace
import json
import re
import shutil
import sqlite3
import threading
import time
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import shape
from shapely.ops import unary_union

from diagnostics.models import DiagnosticRequest, MODULES, NASA_MODULES, nasa_ready
from .config import custom_ready
from .models import JobRequest, rectangle
from .store import Store, QueueFull, Conflict, public_job

ACTIVE = {'queued', 'running'}


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    diagnostics: DiagnosticRequest | None = None
    water: JobRequest | None = None

    @model_validator(mode='after')
    def one_study_area(self):
        self.name = self.name.strip()
        if not self.name or any(ord(c) < 32 for c in self.name):
            raise ValueError('Enter a study-area name without control characters.')
        if self.diagnostics is None and self.water is None:
            raise ValueError('Select at least one diagnostic.')
        if self.water is not None:
            if len(self.name) > 80:
                raise ValueError('Use a study-area name of at most 80 characters for water analysis.')
            self.water.name = self.name
        if self.diagnostics is not None:
            self.diagnostics.name = self.name
            if self.diagnostics.config is not None:
                self.diagnostics.config['name'] = self.name
        if self.diagnostics is not None and self.water is not None:
            if self.diagnostics.mode != 'custom':
                raise ValueError('Combine diagnostics only for the same study area. The Ganjam reference and Fayoum water sample cover different regions.')
            d = unary_union([shape(f['geometry']) for f in self.diagnostics.boundary['features']])
            boundary = self.water.boundary or rectangle(self.water.bbox)
            w = unary_union([shape(f['geometry']) for f in boundary['features']])
            if self.water.mode == 'custom' and self.water.boundary is None:
                if any(abs(a-b) > 1e-6 for a,b in zip(d.bounds,self.water.bbox)):
                    raise ValueError('Water and environmental diagnostics must use the same boundary.')
                self.water.boundary = self.diagnostics.boundary
            elif not d.equals(w):
                raise ValueError('Water and environmental diagnostics must use the same boundary.')
        return self


class Analyses:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data / 'analyses.sqlite3'
        self.queues = {'water': Store(settings.data), 'diagnostics': Store(settings.data / 'diagnostics')}
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, idem TEXT NOT NULL,
                request TEXT NOT NULL, created REAL NOT NULL, phase TEXT NOT NULL,
                UNIQUE(owner,idem))''')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    def records(self, owner=None):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM analyses'+(' WHERE owner=?' if owner is not None else '')+' ORDER BY created DESC',(owner,) if owner is not None else ())]

    @staticmethod
    def child_id(analysis_id, kind):
        return uuid.uuid5(uuid.UUID(hex=analysis_id),kind).hex

    def describe(self, row):
        request = json.loads(row['request'])
        children = []
        for kind in ('diagnostics','water'):
            if request.get(kind) is None: continue
            child_id = self.child_id(row['id'],kind)
            job = self.queues[kind].get(child_id,row['owner'])
            children.append(dict(kind=kind,job=public_job(job) if job else None,modules=request[kind]['modules'] if kind=='diagnostics' else ['water']))
        jobs = [c['job'] for c in children if c['job'] is not None]
        states = [j['status'] for j in jobs]
        if row['phase'] in ('cancelling','cancelled'):
            status = 'running' if any(s in ACTIVE for s in states) else 'partial' if any(s in ('succeeded','partial') for s in states) else 'cancelled'
        elif 'running' in states: status = 'running'
        elif row['phase']=='preparing' or 'queued' in states or len(jobs)<len(children): status = 'queued'
        elif all(s=='succeeded' for s in states): status = 'succeeded'
        elif any(s in ('succeeded','partial') for s in states): status = 'partial'
        elif all(s=='expired' for s in states): status = 'expired'
        elif all(s=='cancelled' for s in states): status = 'cancelled'
        else: status = 'failed'
        active = next((j for j in jobs if j['status']=='running'),None)
        stage = active['stage'] if active else {'queued':'Waiting for a compute slot','succeeded':'All selected diagnostics completed','partial':'Some diagnostics completed · review each module','failed':'Analysis could not complete','cancelled':'Analysis cancelled','expired':'Results expired','running':'Stopping calculation'}[status]
        if row['phase']=='cancelling' and status=='running': stage='Stopping calculation'
        return dict(id=row['id'],name=request['name'],created=row['created'],updated=max([row['created'],*[j['updated'] for j in jobs]]),status=status,stage=stage,
                    modules=[m for c in children for m in c['modules']],children=children,cancel_requested=row['phase'] in ('cancelling','cancelled'),legacy=False)

    def create(self, owner, idem, request):
        body = json.dumps(request,sort_keys=True)
        with self.lock:
            records = self.records()
            old = next((r for r in records if r['owner']==owner and r['idem']==idem),None)
            if old:
                if old['request'] != body: raise Conflict('This submission key was already used with different settings.')
                return self.describe(old)
            active = [r for r in records if self.describe(r)['status'] in ACTIVE]
            if len(active)>=self.settings.max_pending or sum(r['owner']==owner for r in active)>=self.settings.max_user_pending:
                raise QueueFull('The analysis queue is full. Wait for a task to finish or cancel a pending task.')
            row=dict(id=uuid.uuid4().hex,owner=owner,idem=idem,request=body,created=time.time(),phase='preparing')
            with self.connect() as db:
                db.execute('INSERT INTO analyses VALUES(:id,:owner,:idem,:request,:created,:phase)',row)
            # Intent is durable before either child is created. The dispatcher can
            # resume after a process exit without duplicate calculations.
            self.dispatch()
            return self.describe(row)

    def dispatch(self):
        with self.lock:
            for row in self.records():
                request=json.loads(row['request'])
                if row['phase']=='cancelling':
                    for kind,queue in self.queues.items():
                        if request.get(kind) is not None: queue.cancel(self.child_id(row['id'],kind),row['owner'])
                    if self.describe(row)['status'] not in ACTIVE:
                        with self.connect() as db: db.execute("UPDATE analyses SET phase='cancelled' WHERE id=?",(row['id'],))
                    continue
                if row['phase']!='preparing': continue
                ready=True
                for kind in ('diagnostics','water'):
                    payload=request.get(kind)
                    if payload is None: continue
                    queue=self.queues[kind]; child_id=self.child_id(row['id'],kind)
                    if queue.get(child_id,row['owner']) is not None: continue
                    if shutil.disk_usage(queue.data).free < self.settings.min_free_bytes:
                        ready=False; continue
                    try:
                        queue.create(row['owner'],'analysis-'+row['id'],payload,replace(self.settings,data=queue.data),job_id=child_id)
                    except QueueFull:
                        ready=False
                if ready:
                    with self.connect() as db: db.execute("UPDATE analyses SET phase='submitted' WHERE id=?",(row['id'],))

    def list(self, owner):
        records=self.records(owner)
        grouped={self.child_id(r['id'],kind) for r in records for kind in self.queues}
        result=[self.describe(r) for r in records]
        for kind,queue in self.queues.items():
            for row in queue.list(owner):
                if row['id'] in grouped: continue
                job=public_job(row); modules=job['request']['modules'] if kind=='diagnostics' else ['water']
                result.append(dict(id=kind+':'+job['id'],name=job['request']['name'],created=job['created'],updated=job['updated'],status=job['status'],stage=job['stage'],modules=modules,children=[dict(kind=kind,job=job,modules=modules)],cancel_requested=job['cancel_requested'],legacy=True))
        return sorted(result,key=lambda r:r['created'],reverse=True)[:40]

    def cancel(self, analysis_id, owner):
        with self.lock:
            row=next((r for r in self.records(owner) if r['id']==analysis_id),None)
            if row:
                if self.describe(row)['status'] in ACTIVE:
                    with self.connect() as db: db.execute("UPDATE analyses SET phase='cancelling' WHERE id=?",(analysis_id,))
                    row['phase']='cancelling';self.dispatch()
                return self.describe(row)
            match=re.fullmatch(r'(diagnostics|water):([a-f0-9]{32})',analysis_id)
            if match and self.queues[match[1]].get(match[2],owner):
                self.queues[match[1]].cancel(match[2],owner)
                return next(r for r in self.list(owner) if r['id']==analysis_id)
            raise KeyError(analysis_id)


def install(app, settings, owner):
    analyses=Analyses(settings)
    app.state.analyses=analyses
    async def loop():
        last_cleanup = 0
        while True:
            try:
                await asyncio.to_thread(analyses.dispatch)
                if time.time() - last_cleanup > 3600:
                    await asyncio.to_thread(app.state.uploads.cleanup)
                    last_cleanup = time.time()
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Analysis dispatch will retry')
            await asyncio.sleep(2)

    previous_lifespan=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application):
            dispatcher=asyncio.create_task(loop())
            try: yield
            finally:
                dispatcher.cancel()
                with suppress(asyncio.CancelledError): await dispatcher
    app.router.lifespan_context=lifespan

    @app.get('/api/analyses')
    def listing(user: str=Depends(owner)):
        return analyses.list(user)

    @app.post('/api/analyses',status_code=202)
    def submit(payload:AnalysisRequest,user:str=Depends(owner),idempotency_key:Annotated[str,Header()]=''):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}',idempotency_key):
            raise HTTPException(400,'A submission key is required.')
        d,w=payload.diagnostics,payload.water
        if d:
            unavailable=[m for m in d.modules if m in NASA_MODULES and not nasa_ready(m)]
            if d.mode=='custom' and unavailable:
                raise HTTPException(503,'Source access is not yet verified for: '+', '.join(MODULES[m] for m in unavailable))
            if d.mode=='ganjam' and not (settings.data/'diagnostics/sample-ready.json').exists():
                raise HTTPException(503,'The Ganjam reference inputs are being prepared.')
        if w:
            try:w.validate_limits(settings)
            except ValueError as exc:raise HTTPException(422,str(exc)) from exc
            if w.mode=='custom' and not custom_ready(settings):
                raise HTTPException(503,'Water & productivity currently supports the Fayoum sample. Custom-area satellite and weather access is awaiting verification.')
            if w.mode=='sample' and not (settings.data/'sample/ready.json').exists():
                raise HTTPException(503,'The Fayoum sample inputs are being prepared.')
        if shutil.disk_usage(settings.data).free < settings.min_free_bytes:
            raise HTTPException(503,'Result storage is nearly full.')
        try:
            if d: app.state.uploads.pin(d.model_dump(mode='json'),user,settings.retention_days)
            return analyses.create(user,idempotency_key,payload.model_dump(mode='json'))
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except QueueFull as exc:raise HTTPException(429,str(exc)) from exc
        except Conflict as exc:raise HTTPException(409,str(exc)) from exc

    @app.post('/api/analyses/{analysis_id}/cancel')
    def cancel(analysis_id:str,user:str=Depends(owner)):
        try:return analyses.cancel(analysis_id,user)
        except KeyError as exc:raise HTTPException(404,'Analysis not found.') from exc
