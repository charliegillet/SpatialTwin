"""Planar scene geometry. World (x,z) is passed as two GEOS coordinates."""
from __future__ import annotations
import math
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
from .contracts import RoomSceneV1, RoomObject, Wall

EPS=1e-7
def floor_polygon(scene:RoomSceneV1)->Polygon:
    return Polygon(scene.floor, [v.polygon for v in scene.floor_voids])

def footprint(obj:RoomObject)->Polygon:
    angle=math.radians(obj.yaw_deg);c,s=math.cos(angle),math.sin(angle)
    return Polygon([(obj.center[0]+c*x+s*z,obj.center[1]-s*x+c*z)
                    for x,z in [(-obj.width_m/2,-obj.depth_m/2),(obj.width_m/2,-obj.depth_m/2),
                                (obj.width_m/2,obj.depth_m/2),(-obj.width_m/2,obj.depth_m/2)]])

def wall_length(wall:Wall)->float:return math.dist(wall.start,wall.end)

def wall_solids(scene:RoomSceneV1, bound:str='nominal'):
    """Windows remain solid in the ground-plane model; door gaps must reach floor."""
    solids=[]
    for wall in scene.walls:
        length=wall_length(wall)
        if length<EPS:continue
        def width(o):
            if o.width_interval_m and bound in ('pessimistic','optimistic'):
                return o.width_interval_m[0 if bound=='pessimistic' else 1]
            return o.width_m
        gaps=sorted((o.offset_m,o.offset_m+width(o)) for o in scene.openings
                    if o.wall_id==wall.id and o.kind in ('door','passage') and o.sill_m<=EPS)
        cursor=0
        for start,end in gaps+[(length,length)]:
            if start>cursor+EPS:
                a=[wall.start[i]+(wall.end[i]-wall.start[i])*cursor/length for i in range(2)]
                b=[wall.start[i]+(wall.end[i]-wall.start[i])*min(start,length)/length for i in range(2)]
                solids.append(LineString([a,b]).buffer(wall.thickness_m/2,cap_style='flat'))
            cursor=max(cursor,end)
    return solids

def obstacle_polygons(scene:RoomSceneV1):return [footprint(o) for o in scene.objects]+wall_solids(scene)

def free_space(scene:RoomSceneV1,radius:float,pessimistic:bool=True):
    """Sufficient common-path space, or a deliberately loose optimistic superset.

    Shell/walls are fixed *modeled* geometry. Only object translation disks are
    bounded. Unobserved topology cannot support a real-world guarantee.
    """
    room=floor_polygon(scene)
    q=16; padding=radius/math.cos(math.pi/(4*q))
    if pessimistic:
        domain=room.buffer(-padding,quad_segs=q)
        occupied=[footprint(o).buffer((radius+o.uncertainty_radius_m)/math.cos(math.pi/(4*q)),quad_segs=q)
                  for o in scene.objects]
        occupied += [p.buffer(padding,quad_segs=q) for p in wall_solids(scene,'pessimistic')]
    else:
        # Full floor ignores agent-boundary clearance: a superset, never a false blockage.
        domain=room
        occupied=[]
        for obj in scene.objects:
            core=footprint(obj).buffer(-obj.uncertainty_radius_m,join_style='mitre')
            if not core.is_empty:occupied.append(core.buffer(radius,quad_segs=q))
        occupied += [p.buffer(radius,quad_segs=q) for p in wall_solids(scene,'optimistic')]
    return domain.difference(unary_union(occupied))
