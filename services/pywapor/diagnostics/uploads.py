"""Private, bounded source uploads. Ownership is checked before a job can pin them."""
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time
import uuid

MAX_RASTER = 100_000_000
MAX_VECTOR = 5_000_000
MAX_OWNER = 350_000_000
MAX_TOTAL = 2_000_000_000


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def vector_document(value):
    from shapely.geometry import shape
    if not isinstance(value,dict) or value.get('type') != 'FeatureCollection' or not isinstance(value.get('features'),list) or not 1 <= len(value['features']) <= 5000:
        raise ValueError('Use a GeoJSON FeatureCollection with 1–5,000 polygons.')
    features = []
    for feature in value['features']:
        geometry = feature.get('geometry') if isinstance(feature,dict) else None
        try:
            g = shape(geometry)
            w, s, e, n = g.bounds
        except Exception as exc:
            raise ValueError('The vector geometry is incomplete.') from exc
        if g.geom_type not in ('Polygon', 'MultiPolygon') or g.is_empty or not g.is_valid or g.has_z:
            raise ValueError('Use valid two-dimensional polygons, not points or lines.')
        if not all(math.isfinite(x) for x in (w,s,e,n)) or not (-180 <= w < e <= 180 and -85 <= s < n <= 85) or e-w > 180:
            raise ValueError('Use WGS84 polygons between 85°S and 85°N, without crossing the date line.')
        # Attribute tables are unnecessary for spatial stratification.
        features.append({'type':'Feature', 'properties':{}, 'geometry':geometry})
    return {'type':'FeatureCollection', 'features':features}


def inspect_file(path, kind):
    if kind == 'vector':
        doc = vector_document(json.loads(path.read_text()))
        path.write_text(json.dumps(doc, separators=(',', ':'), allow_nan=False))
        return {'features':len(doc['features']), 'crs':'EPSG:4326'}
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    from rasterio.warp import transform_bounds
    with path.open('rb') as f:
        if f.read(4) not in (b'II*\x00',b'MM\x00*',b'II+\x00',b'MM\x00+'):
            raise ValueError('Upload an actual GeoTIFF file.')
    with rasterio.Env(GDAL_CACHEMAX=16_000_000), rasterio.open(path, driver='GTiff') as src:
        if src.driver != 'GTiff' or src.count != 1 or src.width*src.height > 25_000_000:
            raise ValueError('Use a single-band GeoTIFF with at most 25 million input pixels.')
        epsg = src.crs.to_epsg() if src.crs else None
        if epsg not in (4326,3857,6933) and not (epsg and (32601 <= epsg <= 32660 or 32701 <= epsg <= 32760)):
            raise ValueError('Use WGS84, WGS84 UTM, Web Mercator or EPSG:6933.')
        t = src.transform
        if t.b or t.d or t.a <= 0 or t.e >= 0 or src.tags().get('AREA_OR_POINT') == 'Point':
            raise ValueError('Use a north-up PixelIsArea GeoTIFF without rotation.')
        codes = set()
        for y in range(0,src.height,256):
            for x in range(0,src.width,512):
                block=src.read(1,window=Window(x,y,min(512,src.width-x),min(256,src.height-y)),masked=True)
                values=block.compressed();values=values[np.isfinite(values)&(values!=0)]
                if values.size and (values.min()<1 or values.max()>65534 or np.any(values!=np.floor(values))):
                    raise ValueError('Use integer categorical codes 1–65534; zero and declared NoData are excluded.')
                codes.update(int(v) for v in np.unique(values))
                if len(codes)>256:
                    raise ValueError('Use a categorical raster with at most 256 distinct classes.')
        if not codes:
            raise ValueError('The uploaded raster contains no valid land-cover classes.')
        bounds=list(transform_bounds(src.crs,'EPSG:4326',*src.bounds,densify_pts=21))
        if not all(math.isfinite(v) for v in bounds):
            raise ValueError('The raster extent could not be transformed.')
        return {'width':src.width,'height':src.height,'crs':f'EPSG:{epsg}','codes':sorted(codes),'bounds':bounds,
                'source_resolution':[abs(t.a),abs(t.e)],'source_nodata':float(src.nodata) if src.nodata is not None and math.isfinite(src.nodata) else None}


class Uploads:
    def __init__(self, data):
        self.root=Path(data)/'uploads';self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.db=self.root/'uploads.sqlite3'
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
                state TEXT NOT NULL, bytes INTEGER NOT NULL, sha256 TEXT, info TEXT,
                expires REAL NOT NULL, pinned INTEGER NOT NULL DEFAULT 0)''')
        self.db.chmod(0o600)

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=30);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def path(self, key):
        if not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('Invalid upload identifier.')
        return self.root/(key+'.source')

    def cleanup(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for row in db.execute('SELECT id FROM uploads WHERE expires<?',(time.time(),)).fetchall():
                self.path(row['id']).unlink(missing_ok=True)
                db.execute('DELETE FROM uploads WHERE id=?',(row['id'],))

    def reserve(self, owner, kind, name):
        if kind not in ('raster','vector'):raise ValueError('Unsupported source kind.')
        if not name or len(name)>120 or any(ord(c)<32 for c in name):raise ValueError('Use a file name of 1–120 characters.')
        self.cleanup()
        limit=MAX_RASTER if kind=='raster' else MAX_VECTOR
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            own=db.execute('SELECT coalesce(sum(bytes),0),count(*) FROM uploads WHERE owner=?',(owner,)).fetchone()
            total=db.execute('SELECT coalesce(sum(bytes),0) FROM uploads').fetchone()[0]
            if own[0]+limit>MAX_OWNER or own[1]>=20 or total+limit>MAX_TOTAL:
                raise ValueError('Source-upload storage is full. Remove unused files or try again after they expire.')
            key=uuid.uuid4().hex
            db.execute('INSERT INTO uploads(id,owner,kind,name,state,bytes,expires) VALUES(?,?,?,?,?,?,?)',
                       (key,owner,kind,name,'writing',limit,time.time()+3600))
        return key,limit

    def finish(self, key):
        with self.connect() as db:
            row=db.execute('SELECT * FROM uploads WHERE id=?',(key,)).fetchone()
        path=self.path(key);info=inspect_file(path,row['kind'])
        with self.connect() as db:
            db.execute("UPDATE uploads SET state='ready',bytes=?,sha256=?,info=?,expires=? WHERE id=?",
                       (path.stat().st_size,digest(path),json.dumps(info),time.time()+86400,key))
        return self.get(key,row['owner'])

    def get(self,key,owner=None):
        self.path(key)
        with self.connect() as db:
            row=db.execute('SELECT * FROM uploads WHERE id=? AND state=\'ready\' AND expires>?'+(' AND owner=?' if owner is not None else ''),
                           (key,time.time(),owner) if owner is not None else (key,time.time())).fetchone()
        if row is None:raise ValueError('The source file is missing, expired or belongs to a different workspace. Upload it again.')
        value=dict(row);value['info']=json.loads(value['info'])
        return value

    def discard(self,key,owner=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM uploads WHERE id=?'+(' AND owner=?' if owner is not None else ''),(key,owner) if owner is not None else (key,)).fetchone()
            if row and not row['pinned']:
                self.path(key).unlink(missing_ok=True);db.execute('DELETE FROM uploads WHERE id=?',(key,))

    def pin(self, request, owner, retention_days=30):
        land=request['land_cover'];refs=[(r['upload_id'],'raster') for r in land.get('rasters',[])]
        refs += [(key,'vector') for key in (land.get('protected_upload_id'),land.get('oecm_upload_id')) if key]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for key,kind in refs:
                self.path(key)
                row=db.execute("SELECT * FROM uploads WHERE id=? AND owner=? AND kind=? AND state='ready' AND expires>?",(key,owner,kind,time.time())).fetchone()
                if not row or not self.path(key).is_file():raise ValueError('A source file is missing, expired or belongs to another workspace. Upload it again.')
                if kind=='raster' and land.get('crosswalk'):
                    missing=set(json.loads(row['info'])['codes'])-{r['source'] for r in land['crosswalk']}
                    if missing:raise ValueError('The crosswalk is missing source classes: '+', '.join(map(str,sorted(missing))))
            db.executemany('UPDATE uploads SET pinned=1,expires=max(expires,?) WHERE id=?',[(time.time()+(retention_days+2)*86400,key) for key,_ in refs])

    def verified(self,key):
        row=self.get(key);path=self.path(key)
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
            raise ValueError('An uploaded source failed its checksum check.')
        return path,{k:row[k] for k in ('id','kind','name','bytes','sha256','info')}


def public_upload(row):
    return {k:row[k] for k in ('id','kind','name','bytes','sha256','info','expires')}
