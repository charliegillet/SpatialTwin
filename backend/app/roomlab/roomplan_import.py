"""Strict single-room CapturedRoom JSON import; native USDZ is not JSON."""
import math
import numpy as np
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import polygonize, unary_union
from .contracts import RoomDraft, RoomSceneV1, Wall, Opening, RoomObject, Provenance


def _pose(item):
    d=np.asarray(item['dimensions'],dtype=float)
    raw=np.asarray(item['transform'],dtype=float)
    # simd_float4x4 Codable stores four columns, including translation as column 3.
    m=raw.reshape(4,4).T
    if d.shape!=(3,) or not np.isfinite(d).all() or (d<0).any() or (d[:2]<=0).any() or (d>1000).any():raise ValueError('Invalid RoomPlan dimensions.')
    if not np.isfinite(m).all() or not np.allclose(m[3],[0,0,0,1],atol=1e-4):raise ValueError('Invalid RoomPlan column-major transform.')
    if not np.allclose(m[:3,:3].T@m[:3,:3],np.eye(3),atol=.02) or np.linalg.det(m[:3,:3])<.98:
        raise ValueError('RoomPlan transform must be a rigid, unscaled pose.')
    if abs(m[1,1])<.98:raise ValueError('Tilted/multilevel surfaces cannot be flattened into this room editor.')
    return d,m


def import_roomplan(payload: dict) -> RoomDraft:
    if not isinstance(payload,dict) or not isinstance(payload.get('walls'),list) or not payload['walls']:
        raise ValueError('Expected one CapturedRoom JSON object with walls, dimensions and column-major transforms; USDZ and multi-room structures are not supported.')
    if len(payload['walls'])>100 or len(payload.get('objects',[]))>200:raise ValueError('RoomPlan export exceeds room limits.')
    prov=Provenance(source='geometry_fit',visibility='partial',note='Imported RoomPlan sensor estimate in meters; not an independently measured dimension.')
    stories={item.get('story',0) for key in ('walls','doors','windows','openings','objects','floors') for item in payload.get(key,[])}
    if len(stories)>1:raise ValueError('Multiple stories must be imported separately.')
    if len(payload.get('floors',[]))>1:raise ValueError('Import only one floor surface at a time.')
    walls=[];ys=[];wall_identifiers={}
    for i,item in enumerate(payload['walls']):
        if item.get('curve'):raise ValueError('Curved RoomPlan walls need manual conversion; no straight-wall approximation was applied.')
        if item.get('polygonCorners'):raise ValueError('Nonuniform wall polygons require manual conversion.')
        d,m=_pose(item);c=m[:3,3];a=c-m[:3,0]*d[0]/2;b=c+m[:3,0]*d[0]/2;ys.append(c[1]-d[1]/2)
        walls.append(Wall(id=f'wall-rp-{i+1}',start=[float(a[0]),float(a[2])],end=[float(b[0]),float(b[2])],height_m=float(d[1]),thickness_m=max(.08,float(d[2])),provenance=prov))
        if item.get('identifier'):wall_identifiers[item['identifier']]=walls[-1]
    if max(ys)-min(ys)>.15:raise ValueError('Wall bases span multiple levels; import one level at a time.')
    # Snap only nearby endpoints and disclose the operation. Never invent a convex-hull room.
    endpoints=[p for w in walls for p in (w.start,w.end)]
    groups=[]
    for p in endpoints:
        group=next((g for g in groups if math.dist(p,g[0])<=.12),None)
        if group is None:groups.append([p])
        else:group.append(p)
    for group in groups:
        mean=np.mean(group,axis=0).tolist()
        for p in group:p[:]=mean
    polys=list(polygonize(unary_union([LineString([w.start,w.end]) for w in walls])))
    if not polys or any(p.interiors for p in polys):raise ValueError('Walls do not form one closed, hole-free room. Import one room or correct wall joins first.')
    poly=unary_union(polys)
    if poly.geom_type!='Polygon' or poly.interiors:raise ValueError('Walls do not form one closed, hole-free room. Import one room or correct wall joins first.')
    poly=poly.simplify(1e-6,preserve_topology=True)
    floor=[[float(x),float(z)] for x,z in list(poly.exterior.coords)[:-1]]
    for floor_surface in payload.get('floors',[]):
        corners=floor_surface.get('polygonCorners',[])
        if corners:
            matrix=np.asarray(floor_surface['transform'],dtype=float).reshape(4,4).T
            vertices=np.asarray(corners,dtype=float)
            if vertices.ndim!=2 or vertices.shape[1]!=3 or len(vertices)<3 or not np.isfinite(vertices).all():raise ValueError('Invalid floor corners.')
            world=(matrix@np.column_stack([vertices,np.ones(len(vertices))]).T).T
            if not np.isfinite(world).all() or np.ptp(world[:,1])>.08:raise ValueError('Floor is not a single horizontal level.')
            observed_floor=Polygon(world[:,[0,2]])
            if not observed_floor.is_valid or not poly.buffer(.15).covers(observed_floor) or not observed_floor.buffer(.15).covers(poly):
                raise ValueError('Observed floor differs from the closed wall outline. Convert voids and irregular boundaries explicitly.')
    for w in walls:
        if not poly.boundary.buffer(.13).covers(LineString([w.start,w.end])):w.role='partition'
    # Canonical shell order follows floor vertices; capture array order need not.
    shell=[w for w in walls if w.role=='shell'];partitions=[w for w in walls if w.role!='shell'];ordered=[]
    for i,a in enumerate(floor):
        b=floor[(i+1)%len(floor)]
        original=next((w for w in shell if LineString([w.start,w.end]).buffer(.13).covers(LineString([a,b])) and abs(LineString([w.start,w.end]).length-math.dist(a,b))<.25),None)
        if original is None or original in ordered:raise ValueError('Wall boundary segmentation requires manual conversion.')
        original.start=a;original.end=b;ordered.append(original)
    walls=ordered+partitions
    openings=[]
    for key,kind in [('doors','door'),('windows','window'),('openings','passage')]:
        for item in payload.get(key,[]):
            d,m=_pose(item);center=[float(m[0,3]),float(m[2,3])]
            wall=wall_identifiers.get(item.get('parentIdentifier'))
            if wall is None:wall=min(walls,key=lambda w:LineString([w.start,w.end]).distance(Point(center)))
            line=LineString([wall.start,wall.end]);offset=line.project(Point(center))-float(d[0])/2
            if line.distance(Point(center))>.25 or offset<-.12 or offset+d[0]>line.length+.12:
                raise ValueError('An opening cannot be attached to its observed wall; no geometry was silently moved.')
            sill=max(0.,float(m[1,3]-d[1]/2-min(ys))) if kind=='window' else 0.
            openings.append(Opening(id=f'opening-rp-{len(openings)+1}',wall_id=wall.id,kind=kind,
                offset_m=max(0.,offset),width_m=min(float(d[0]),line.length-max(0.,offset)),height_m=float(d[1]),sill_m=sill,provenance=prov))
    objects=[]
    for i,item in enumerate(payload.get('objects',[])):
        d,m=_pose(item)
        if d[2]<=0:raise ValueError('Object depth must be positive.')
        category=item.get('category','furniture')
        if isinstance(category,dict):category=next(iter(category),'furniture')
        category=str(category)[:80]
        objects.append(RoomObject(id=f'obj-rp-{i+1}',label=category[:160],category=category,
            center=[float(m[0,3]),float(m[2,3])],width_m=float(d[0]),height_m=float(d[1]),depth_m=float(d[2]),
            yaw_deg=math.degrees(math.atan2(float(-m[2,0]),float(m[0,0]))),
            movable=category not in ('storage','refrigerator','oven','sink','stove','stairs'),provenance=prov))
    draft=RoomDraft(name=str(payload.get('name','Imported RoomPlan room'))[:160],floor=floor,walls=walls,openings=openings,objects=objects,
        topology_review_required=True,notes=['RoomPlan JSON sensor estimates in meters. Wall endpoints within 12 cm were snapped to close the perimeter.',
        'Review topology, glass, stairs and furniture. Native curves, multiple levels and disconnected rooms are rejected.',
        'No video evidence or articulated door poses were imported. Verify a measured anchor and an independent held-out dimension.'])

    from .validation import validate_scene
    issues=validate_scene(RoomSceneV1(**draft.model_dump(),scene_id='roomplan-import-check',geometry_source='geometry_fit')).issues
    errors=[i for i in issues if i.severity=='error' and i.code!='topology_review_required']
    if errors:raise ValueError('RoomPlan geometry needs correction before import: '+', '.join(sorted({i.code for i in errors})))
    return draft
