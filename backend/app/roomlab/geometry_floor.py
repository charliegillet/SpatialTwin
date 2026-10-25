"""Explicitly selected coplanar evidence landmarks become a measured floor proposal."""
import numpy as np
from shapely.geometry import Polygon
from .contracts import GeometryReport, GeometryFloorRequest, RoomDraft, Wall, Provenance


def fit_floor(report: GeometryReport, request: GeometryFloorRequest) -> RoomDraft:
    if not request.measurement_confirmed or not request.topology_confirmed:
        raise ValueError('Confirm the measured first edge and that the selected outline excludes drop-offs.')
    if len(set(request.point_ids))!=len(request.point_ids):raise ValueError('Choose distinct floor corners in perimeter order.')
    catalog={p.id:p for p in report.points}
    if any(i not in catalog for i in request.point_ids):raise ValueError('A selected point is not in this reconstruction.')
    xyz=np.array([catalog[i].xyz for i in request.point_ids],dtype=float)
    origin=xyz[0];axis=xyz[1]-origin;length=np.linalg.norm(axis)
    if length<1e-6:raise ValueError('First edge is too short.')
    _,_,v=np.linalg.svd(xyz-xyz.mean(axis=0));normal=v[-1]
    residual=np.max(np.abs((xyz-origin)@normal))
    scale=request.first_edge_measured_m/length
    if residual*scale>.08:raise ValueError('Selected floor corners are not coplanar within 8 cm. Choose floor points from one level.')
    axis=axis/length;across=np.cross(axis,normal);across/=np.linalg.norm(across)
    floor=[[(float((p-origin)@axis)*scale),float((p-origin)@across)*scale] for p in xyz]
    polygon=Polygon(floor)
    if not polygon.is_valid or polygon.area<.1:raise ValueError('Floor outline crosses itself or has too little area. Select corners in perimeter order.')
    prov=Provenance(source='geometry_fit',visibility='partial',note='Floor perimeter selected from sparse COLMAP landmarks; first edge scaled by a user-supplied measurement. Wall height is an estimate.')
    return RoomDraft(name='Geometry-backed floor proposal',floor=floor,
        walls=[Wall(id=f'wall-{i+1}',start=p,end=floor[(i+1)%len(floor)],height_m=request.wall_height_m,provenance=prov) for i,p in enumerate(floor)],
        topology_review_required=True,
        notes=[f'COLMAP sparse geometry. Scale={scale:.6g} m/reconstruction unit; selected-plane maximum residual={residual*scale:.3f} m.',
               'User-selected floor outline; review all corners, openings, drop-offs and missing furniture before clearance analysis.',
               'Only the measured first edge is scale evidence. Wall height and remaining geometry need independent verification.'])


def fit_object(report, floor_request, scene, request):
    """Fit a conservative OBB to manually identified object points in the floor frame."""
    import math
    from .contracts import RoomObject
    if not request.floor_supported_confirmed:raise ValueError('Confirm these points belong to one floor-supported object.')
    if len(set(request.point_ids))!=len(request.point_ids):raise ValueError('Select distinct object landmarks.')
    catalog={p.id:p for p in report.points}
    if any(i not in catalog for i in request.point_ids):raise ValueError('Object point is not in this reconstruction.')
    anchors=np.array([catalog[i].xyz for i in floor_request.point_ids],dtype=float)
    origin=anchors[0];axis=anchors[1]-origin;scale=floor_request.first_edge_measured_m/np.linalg.norm(axis);axis/=np.linalg.norm(axis)
    _,_,v=np.linalg.svd(anchors-anchors.mean(axis=0));normal=v[-1];across=np.cross(axis,normal);across/=np.linalg.norm(across)
    # Retain the same XZ projection as fit_floor. Choose height sign from known camera centers.
    camera_sides=[np.dot(np.array(c.center)-origin,normal) for c in report.cameras]
    up_sign=1 if not camera_sides or np.median(camera_sides)>=0 else -1
    xyz=np.array([catalog[i].xyz for i in request.point_ids],dtype=float)
    flat=np.column_stack([(xyz-origin)@axis,(xyz-origin)@across])*scale
    height_values=((xyz-origin)@normal)*scale*up_sign
    if np.min(height_values)<-.12 or np.max(height_values)<.05:raise ValueError('Object points lie below the selected floor or do not constrain object height.')
    from shapely.geometry import MultiPoint
    rectangle=MultiPoint(flat).minimum_rotated_rectangle
    if rectangle.geom_type!='Polygon' or rectangle.area<.0025:raise ValueError('Object landmarks do not span a usable footprint.')
    if not Polygon(scene.floor,[v.polygon for v in scene.floor_voids]).buffer(.01).covers(rectangle):
        raise ValueError('Object footprint crosses the floor boundary or a void. Select tighter landmarks and review topology.')
    corners=np.array(list(rectangle.exterior.coords)[:-1]);edge=corners[1]-corners[0];second=corners[2]-corners[1]
    return RoomObject(id='obj-geometry-'+__import__('uuid').uuid4().hex[:12],label=request.label,category=request.category,
        center=rectangle.centroid.coords[0],width_m=float(np.linalg.norm(edge)),depth_m=float(np.linalg.norm(second)),
        height_m=float(np.max(height_values)),yaw_deg=math.degrees(math.atan2(-edge[1],edge[0])),movable=request.movable,
        uncertainty_radius_m=.2,provenance=Provenance(source='geometry_fit',visibility='partial',evidence_frame_ids=[],
        note='OBB fitted to user-selected sparse object landmarks in the measured floor frame. Missing surfaces may extend beyond this fit; 0.2m is a heuristic margin, not a measured error bound. No element-specific image citations were assigned.'))
