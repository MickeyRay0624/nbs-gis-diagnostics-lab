"""Online land inputs, comparable-area change accounting and whole-AOI forest strata."""
import csv
import json
import math
from types import SimpleNamespace

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from shapely.geometry import mapping

from nbs_prepare.core import json_bytes, read_boundary, grid_for
from nbs_prepare.sources import crop_cog
from nbs_gis.fragmentation import classify_forest, protection_grid
from .uploads import Uploads

WORLD = [(10,"Tree cover","#006400"),(20,"Shrubland","#ffbb22"),(30,"Grassland","#ffff4c"),(40,"Cropland","#f096ff"),(50,"Built-up","#fa0000"),(60,"Bare / sparse vegetation","#b4b4b4"),(70,"Snow and ice","#f0f0f0"),(80,"Permanent water bodies","#0064c8"),(90,"Herbaceous wetland","#0096a0"),(95,"Mangroves","#00cf75"),(100,"Moss and lichen","#fae6a0")]
FRAGMENT = [(0,"Non-forest","#efede2"),(1,"Patch","#d64233"),(2,"Edge","#e6ab36"),(3,"Internal clearing","#b752a3"),(4,"Core","#286845")]
STRATA = [(0,"All"),(1,"Protected"),(2,"OECM"),(3,"Outside supplied polygons")]


def spec(id, title, period, categories, note):
    return dict(id=id,title=title,period=str(period),unit="class",operation="identity",inputs=[],palette="sequential",interpretation=note,categories=[dict(value=c,label=n,color=color) for c,n,color in categories])


def reclassify(raw, rows):
    mapping_={r['source']:r['code'] for r in rows}
    missing=set(int(v) for v in np.unique(raw))-{0}-set(mapping_)
    if missing:
        raise ValueError('Crosswalk does not cover source classes: '+', '.join(map(str,sorted(missing))))
    lut=np.zeros(65536,dtype='uint16')
    for key,value in mapping_.items():lut[key]=value
    return lut[raw]


def read_aligned(path, transform, shape):
    # Read the mask as well as declared NoData: internal TIFF masks also mean unknown.
    with rasterio.open(path) as src:
        source=src.read(1,masked=True).astype('float32').filled(0)
        source[~np.isfinite(source)]=0
        out=np.zeros(shape,dtype='uint16')
        reproject(source,out,src_transform=src.transform,src_crs=src.crs,src_nodata=0,
                  dst_transform=transform,dst_crs='EPSG:6933',dst_nodata=0,
                  resampling=Resampling.nearest,num_threads=1,warp_mem_limit=32)
    return out


def pairs(years):
    years=sorted(years)
    return list(zip(years[:-1],years[1:]))+([(years[0],years[-1])] if len(years)>2 else [])


def transition_rows(a,b,classes,start,end,cell_ha,strata=None):
    """Every matrix cell is explicit; gross gain/loss exclude persistence."""
    valid=(a>0)&(b>0)
    transitions=[];balances=[]
    for group,label in STRATA if strata is not None else STRATA[:1]:
        mask=valid if group==0 else valid&(strata==group)
        encoded=a[mask].astype('int64')*65536+b[mask]
        codes,counts=np.unique(encoded,return_counts=True)
        areas={int(code):int(n)*cell_ha for code,n in zip(codes,counts)}
        common=float(mask.sum())*cell_ha
        for x,xname,_ in classes:
            before=sum(areas.get(x*65536+y,0) for y,_,_ in classes)
            after=sum(areas.get(y*65536+x,0) for y,_,_ in classes)
            same=areas.get(x*65536+x,0)
            balances.append(dict(start_year=start,end_year=end,stratum=label,code=x,class_name=xname,
                before_ha=before,after_ha=after,persistence_ha=same,gross_gain_ha=after-same,
                gross_loss_ha=before-same,net_ha=after-before,common_valid_ha=common))
            for y,yname,_ in classes:
                area=areas.get(x*65536+y,0)
                transitions.append(dict(start_year=start,end_year=end,stratum=label,from_code=x,to_code=y,
                    from_class=xname,to_class=yname,area_ha=area,pixels=round(area/cell_ha),common_valid_ha=common))
        if not np.isclose(sum(r['net_ha'] for r in balances if r['start_year']==start and r['end_year']==end and r['stratum']==label),0,atol=1e-6):
            raise ValueError('Class change conservation failed.')
    return transitions,balances


def derived(row):
    row=dict(row)
    if row['stratum']=='Unprotected':row['stratum']='Outside supplied polygons'
    forest=row['forest_ha'];land=row['landscape_ha']
    row.update(patch_pct=100*row['patch_ha']/forest if forest else None,
               edge_pct=100*row['edge_ha']/forest if forest else None,
               core_pct=100*row['core_ha']/forest if forest else None,
               perforation_pct=100*row['clearing_ha']/forest if forest else None,
               TE_km=row['TE_m']/1000,
               edge_per_forest_ha=row['TE_m']/forest if forest else None,
               largest_patch_forest_pct=100*row['largest_patch_ha']/forest if forest else None)
    if not land:row.update(PLAND=None,ED=None,LPI=None)
    if not row['NP']:row.update(MPS_ha=None,MPE=None,MSI=None,AWMSI=None)
    return row


def forest_changes(a,b,start,end,cell_ha,strata=None):
    valid=(a!=255)&(b!=255);rows=[]
    for group,label in STRATA if strata is not None else STRATA[:1]:
        mask=valid if not group else valid&(strata==group)
        for name,codes in [('Forest',[1,2,4]),('Patch',[1]),('Edge',[2]),('Core',[4]),('Internal clearing',[3])]:
            before=np.isin(a,codes)&mask;after=np.isin(b,codes)&mask
            gain=float((after&~before).sum())*cell_ha;loss=float((before&~after).sum())*cell_ha
            rows.append(dict(start_year=start,end_year=end,stratum=label,component=name,
                before_ha=float(before.sum())*cell_ha,after_ha=float(after.sum())*cell_ha,
                gross_gain_ha=gain,gross_loss_ha=loss,net_ha=gain-loss,common_valid_ha=float(mask.sum())*cell_ha))
    return rows


def run_land(publisher,request,reference,ctx=None):
    options=request['land_cover'];resolution=options['resolution'];uploaded=options.get('source')=='uploaded'
    aoi,area_aoi=read_boundary(json_bytes(publisher.boundary))
    transform,shape=grid_for(aoi,resolution,6933);crs=rasterio.crs.CRS.from_epsg(6933)
    if np.prod(shape)>8_000_000:raise ValueError('The aligned analysis grid exceeds eight million cells.')
    uploads=Uploads(publisher.folder.parent.parent)
    records=[];raws={}
    if uploaded:
        for item in sorted(options['rasters'],key=lambda r:r['year']):
            path,record=uploads.verified(item['upload_id']);records.append(dict(role='land-cover',year=item['year'],**record))
            raws[item['year']]=read_aligned(path,transform,shape)
        rows=options['crosswalk']
        source=dict(id='uploaded-land-cover',name=options['source_name'],version=', '.join(map(str,raws)),licence='Supplied by the user; original source terms apply',url='',description='Private GeoTIFF inputs, checked against recorded SHA-256 digests before calculation. Source metadata is in input-manifest.json.',resolution=f'User source grids · {resolution} m analysis grid')
        forest=options.get('forest_codes') or []
        note='Differences depend on source comparability, class definitions and coverage. A finer analysis grid does not increase source detail.'
    elif request['mode']=='ganjam':
        with (reference/'glcfcs/crosswalk.csv').open() as f:
            default=[dict(source=int(r['source_code']),code=int(r['target_code']),name=r['target_name'],color=r['color']) for r in csv.DictReader(f)]
        rows=options.get('crosswalk') or default
        for year in sorted(options.get('years') or [2002,2012,2022]):
            path=reference/f'glcfcs/ganjam_{year}_50m.tif'
            # Retain the exact prepared grid at 50 m; the reference boundary is identical.
            with rasterio.open(path) as src:
                if resolution==50:transform=src.transform;shape=(src.height,src.width)
            raws[year]=read_aligned(path,transform,shape)
        forest=options.get('forest_codes') or [2]
        source=dict(id='glcfcs-online',name='GLC-FCS30D prepared Ganjam inputs',version=', '.join(map(str,raws)),licence='CC BY 4.0',url='https://doi.org/10.5194/essd-16-1353-2024',description='Prepared 50 m Ganjam categorical inputs, reclassified and recalculated on this server.',resolution=f'30 m source · prepared 50 m · {resolution} m analysis grid')
        note='The Ganjam source has already been prepared at 50 m; this run preserves or coarsens that grid. It does not reconstruct 30 m observations.'
    else:
        rows=options.get('crosswalk') or [dict(source=c,code=c,name=n,color=color) for c,n,color in WORLD]
        w,s,e,n=aoi.bounds
        for year in sorted(options.get('years') or [2020,2021]):
            version={2020:'v100',2021:'v200'}[year];data=np.zeros(shape,dtype='uint16')
            for y in range(math.floor(s/3)*3,math.ceil(n/3)*3,3):
                for x in range(math.floor(w/3)*3,math.ceil(e/3)*3,3):
                    tile=f"{'N' if y>=0 else 'S'}{abs(y):02d}{'E' if x>=0 else 'W'}{abs(x):03d}"
                    url=f'https://esa-worldcover.s3.eu-central-1.amazonaws.com/{version}/{year}/map/ESA_WorldCover_10m_{year}_{version}_{tile}_Map.tif'
                    part=crop_cog(ctx,url,[1],transform,shape,6933,factor=max(1,resolution//10))[0]
                    valid=np.isfinite(part)&(part>0)
                    if not np.isin(part[valid],[c[0] for c in WORLD]).all():raise ValueError('Unexpected WorldCover class.')
                    data[valid]=part[valid].astype('uint16')
            raws[year]=data
        forest=options.get('forest_codes') or ([10,95] if options['include_mangroves'] else [10])
        source=dict(id='worldcover-online',name='ESA WorldCover',version=', '.join(f'{y} '+{2020:'v100',2021:'v200'}[y] for y in raws),licence='CC BY 4.0',url='https://esa-worldcover.org/en/data-access',description='Public COG windows, nearest-neighbour sampled. © ESA WorldCover project 2020/2021 / Contains modified Copernicus Sentinel data processed by ESA WorldCover consortium.',resolution=f'10 m source · {resolution} m analysis grid')
        note='WorldCover 2020 and 2021 use different algorithms. Mapped differences include algorithm effects and cannot be interpreted solely as real land-cover change.'
    classes=sorted({r['code']:(r['name'],r['color']) for r in rows if r['code']!=0}.items())
    classes=[(c,*v) for c,v in classes]
    inside=rasterize([(mapping(area_aoi),1)],out_shape=shape,transform=transform).astype(bool)
    weights=np.where(inside,resolution**2/1e6,0).astype('float32')
    rasters={}
    for year,raw in raws.items():
        raw[~inside]=0;rasters[year]=reclassify(raw,rows)
    del raws
    if not any(np.any(a>0) for a in rasters.values()):raise ValueError('No classified cells inside the study area.')
    paths={}
    for role in ('protected','oecm'):
        key=options.get(role+'_upload_id')
        if key:
            path,record=uploads.verified(key);records.append(dict(role=role,year=None,**record));paths[role]=path
            (publisher.out/(role+'.geojson')).write_bytes(path.read_bytes())
    strata=protection_grid(paths.get('protected'),paths.get('oecm'),SimpleNamespace(crs=crs,height=shape[0],width=shape[1],transform=transform))
    protection='No protection polygons supplied; protection status is not inferred.' if strata is None else 'Protected overrides OECM on overlaps. The remainder is outside the supplied polygons; incomplete inputs cannot establish that it is unprotected.'
    method=[f'Nearest-neighbour categorical comparison on an EPSG:6933 square {resolution} m grid.',
            'Pixel-centre mask; areas equal included cell counts times cell area. Pairwise change uses only cells valid in both periods.',protection,note]
    publisher.source(source)
    def module(mid):
        return dict(id=mid,title={'lulc':'Land-cover change','fragmentation':'Forest fragmentation'}[mid],status='available',sources=[source['id']],method=method,limitations=[note,protection],fieldChecks=['Can local observations corroborate these patterns?'])
    landinfo=dict(resolution_m=resolution,years=sorted(rasters),crosswalk=rows,forest_codes=forest,
                  edge_width_m=options['edge_width_m'],count_boundary_as_edge=options['count_boundary_as_edge'],
                  protection_note=options.get('protection_note',''),protection_method=protection,inputs=records)
    publisher.land=landinfo
    (publisher.out/'input-manifest.json').write_bytes(json_bytes(landinfo))
    mid='lulc' if 'lulc' in request['modules'] else 'fragmentation'
    publisher.table(mid,'Class crosswalk','class-crosswalk.csv',[dict(source_code=r['source'],target_code=r['code'],target_name=r['name'],color=r['color'],forest=r['code'] in forest) for r in rows])
    if 'lulc' in request['modules']:
        for year,data in rasters.items():
            values=data.astype('float32');values[data==0]=np.nan
            publisher.add('lulc',spec(f'cover-{year}',f'Land cover · {year}',year,classes,note),values,weights,transform,crs,source['resolution'])
        transitions=[];balances=[]
        for start,end in pairs(rasters):
            a,b=rasters[start],rasters[end];valid=(a>0)&(b>0)
            values=np.where(valid,(a!=b).astype('float32'),np.nan)
            publisher.add('lulc',spec(f'change-{start}-{end}',f'Class change · {start}–{end}',f'{start}–{end}',[(0,'Same mapped class','#d8ded8'),(1,'Different mapped class','#cf7058')],note),values,weights,transform,crs,source['resolution'])
            tr,ba=transition_rows(a,b,classes,start,end,resolution**2/10000,strata);transitions.extend(tr);balances.extend(ba)
            publisher.checks.append(dict(module='lulc',layer=f'{start}-{end}',check='Common-footprint matrix area and net class-area conservation',passed=True))
        publisher.table('lulc','Land-cover transitions','land-cover-transitions.csv',transitions)
        publisher.table('lulc','Gross gains, losses and net change','land-cover-balance.csv',balances)
        publisher.modules.append(module('lulc'))
    if 'fragmentation' in request['modules']:
        metrics=[];classified={}
        for year,data in rasters.items():
            out,yearrows,qa=classify_forest(data,forest,resolution,options['edge_width_m'],strata=strata,count_boundary=options['count_boundary_as_edge'])
            if not qa['class_conservation']:raise ValueError('Forest class conservation failed.')
            publisher.checks.append(dict(module='fragmentation',layer=f'forest-{year}',check='Forest pixels conserved across patch, edge and core; whole AOI classified before strata',passed=True))
            classified[year]=out
            values=out.astype('float32');values[out==255]=np.nan
            publisher.add('fragmentation',spec(f'fragmentation-{year}',f'Forest structure · {year}',year,FRAGMENT,'Internal clearings are non-forest; NoData holes are unknown. Forest connectivity: 8 neighbours; clearing connectivity: 4.'),values,weights,transform,crs,source['resolution'])
            metrics.extend(dict(year=year,**derived(row)) for row in yearrows)
        changes=[]
        for start,end in pairs(classified):changes.extend(forest_changes(classified[start],classified[end],start,end,resolution**2/10000,strata))
        publisher.table('fragmentation','Forest metrics','forest-metrics.csv',metrics)
        publisher.table('fragmentation','Forest group changes on common coverage','forest-changes.csv',changes)
        m=module('fragmentation');m['method']=[*method,f"Forest target classes {forest}; edge width {options['edge_width_m']} m; boundary counted as edge: {options['count_boundary_as_edge']}.",
            'Classify the entire AOI before splitting statistics. Patch counts and shape means assign whole patches to their majority stratum (ties: Protected, OECM, remainder). Area and total edge allocate by pixel; LPI uses actual patch intersections.',
            'Patch, edge and core percentages use forest area. Perforation percentage = internal-clearing area / forest area × 100; clearings remain non-forest. TE_km = TE_m / 1000. Edge/forest area is m/ha. Ratios with zero denominators are missing.',
            'Group-change charts use common valid cells for each pair. Structures are classified on each full period first; this preserves ecological context outside the comparison footprint.']
        publisher.modules.append(m)
