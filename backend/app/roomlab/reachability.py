"""Bounded deterministic search, continuous witness check and honest bound outcomes."""
from __future__ import annotations
import heapq,math
from shapely.geometry import Point,LineString,Polygon
from .contracts import RoomSceneV1,SolveRequest,SolveResult,geometry_hash
from .geometry import free_space,obstacle_polygons,EPS
from .validation import validate_scene

def components(geometry):
    if geometry.geom_type=='Polygon':return [geometry]
    return [g for g in getattr(geometry,'geoms',[]) if g.geom_type=='Polygon' and g.area>EPS]

def same_component(free,start,goal):
    return next((p for p in components(free) if p.contains(Point(start)) and p.contains(Point(goal))),None)

def find_path(free,start,goal):
    region=same_component(free,start,goal)
    if region is None:return None
    # A straight witness is both fast and exact for the modeled polygons.
    direct=LineString([start,goal])
    if region.contains(direct):return [start,goal]
    minx,minz,maxx,maxz=region.bounds
    step=max(.08,max(maxx-minx,maxz-minz)/110)
    nx,nz=int((maxx-minx)/step)+1,int((maxz-minz)/step)+1
    nodes={};coords={};counter=0
    for ix in range(nx+1):
        for iz in range(nz+1):
            p=(minx+ix*step,minz+iz*step)
            if region.contains(Point(p)):nodes[ix,iz]=counter;coords[counter]=p;counter+=1
    if not coords:return None
    nodes_by_id={v:k for k,v in nodes.items()}
    coords[counter]=tuple(start);source=counter;coords[counter+1]=tuple(goal);target=counter+1
    terminal={}
    for terminal_id in (source,target):
        near=sorted((math.dist(coords[terminal_id],p),i) for i,p in coords.items() if i<counter)[:40]
        terminal[terminal_id]=[i for _,i in near if region.contains(LineString([coords[terminal_id],coords[i]]))]
    reverse={}
    for t,ns in terminal.items():
        for n in ns:reverse.setdefault(n,[]).append(t)
    queue=[(0.,source)];distance={source:0.};previous={};visited=set()
    while queue:
        _,node=heapq.heappop(queue)
        if node in visited:continue
        if node==target:break
        visited.add(node)
        if node>=counter:neighbors=terminal[node]
        else:
            ix,iz=nodes_by_id[node]
            neighbors=[nodes[key] for dx,dz in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)] if (key:=(ix+dx,iz+dz)) in nodes]
            neighbors+=reverse.get(node,[])
        for other in neighbors:
            if not region.contains(LineString([coords[node],coords[other]])):continue
            cost=distance[node]+math.dist(coords[node],coords[other])
            if cost<distance.get(other,float('inf')):
                distance[other]=cost;previous[other]=node
                heapq.heappush(queue,(cost+math.dist(coords[other],coords[target]),other))
    if target not in distance:return None
    route=[target]
    while route[-1]!=source:route.append(previous[route[-1]])
    raw=[coords[n] for n in reversed(route)]
    # Greedy shortcut only after segment containment checks, including diagonals.
    path=[raw[0]];i=0
    while i<len(raw)-1:
        j=len(raw)-1
        while j>i+1 and not region.contains(LineString([raw[i],raw[j]])):j-=1
        path.append(raw[j]);i=j
    return path if region.contains(LineString(path)) else None

def solve(scene:RoomSceneV1,request:SolveRequest)->SolveResult:
    assumptions=['Flat floor and circular holonomic agent; no turning, steps or headroom model.',
                 'Guarantees apply only to the modeled fixed shell and bounded object translation; unseen topology is not verified.',
                 'Opening widths vary from fixed offsets; unmodeled camera, global scale and measurement errors are not propagated.',
                 f'Margin {request.margin_m:.3f} m; positive-yaw convention matches Three.js.']
    base=dict(scene_revision=scene.scene_revision,geometry_hash=geometry_hash(scene),assumptions=assumptions)
    report=validate_scene(scene)
    if not report.valid:return SolveResult(**base,status='INVALID_SCENE',message='Correct the geometry issues before solving.')
    if scene.calibration is None:return SolveResult(**base,status='UNSCALED',message='Add a measured reference before a metre-based clearance experiment.')
    if not Polygon(scene.floor).contains(Point(request.start)) or not Polygon(scene.floor).contains(Point(request.goal)):
        return SolveResult(**base,status='INVALID_SCENE',message='Start and goal centres must be inside the modeled floor.')
    if math.dist(request.start,request.goal)<EPS:return SolveResult(**base,status='INVALID_SCENE',message='Choose distinct start and goal points.')
    radius=request.agent_diameter_m/2+request.margin_m
    pess=free_space(scene,radius,True);opt=free_space(scene,radius,False)
    shapes=[]
    for obj in scene.objects:
        from .geometry import footprint
        shapes.append([list(p) for p in footprint(obj).buffer((radius+obj.uncertainty_radius_m)/math.cos(math.pi/64),quad_segs=16).exterior.coords])
    path=find_path(pess,request.start,request.goal)
    if path:
        line=LineString(path);obstacles=obstacle_polygons(scene)
        clearance=min([line.distance(p) for p in obstacles]+[line.distance(Polygon(scene.floor).boundary)])
        return SolveResult(**base,status='ROBUST_PASS',message='A continuously checked common path exists within the stated model bounds.',
            path=[list(p) for p in path],path_length_m=line.length,minimum_clearance_m=max(0.,clearance),obstacles=shapes)
    if same_component(opt,request.start,request.goal) is None:
        return SolveResult(**base,status='ROBUST_BLOCKED',message='Start and goal are disconnected even in the optimistic modeled free space.',obstacles=shapes)
    return SolveResult(**base,status='INCONCLUSIVE',message='No conservative path was found; this does not prove blockage.',obstacles=shapes,
        evidence_requests=['Measure the narrowest gap on the desired route or reduce uncertain object translation bounds.'])
