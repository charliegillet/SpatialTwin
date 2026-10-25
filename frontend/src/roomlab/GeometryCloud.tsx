import { useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { Html, Line, OrbitControls } from '@react-three/drei';
import type { GeometryReport } from './contracts.generated';

export function GeometryCloud({report,selected,onSelect,onClose}:{report:GeometryReport;selected:number[];onSelect:(id:number)=>void;onClose:()=>void}) {
 const data=useMemo(()=>{
  const all=report.points;const axes=[0,1,2].map(i=>all.map(p=>p.xyz[i]).sort((a,b)=>a-b));
  const min=axes.map(v=>v[Math.floor(v.length*.02)]),max=axes.map(v=>v[Math.min(v.length-1,Math.floor(v.length*.98))]);
  const center=min.map((v,i)=>(v+max[i])/2);const scale=12/Math.max(...max.map((v,i)=>v-min[i]),.001);
  const project=(v:number[])=>v.map((x,i)=>(x-center[i])*scale) as [number,number,number];
  return {positions:new Float32Array(all.flatMap(p=>project(p.xyz))),colors:new Float32Array(all.flatMap(p=>p.rgb.map(c=>c/255))),project};
 },[report]);
 const chosen=selected.map(id=>report.points.find(p=>p.id===id)).filter(p=>!!p);
 return <div className="rl-geometry-cloud" role="region" aria-label="Sparse camera reconstruction">
  <div className="rl-geometry-cloud-header"><div><strong>Sparse reconstruction</strong><p>{report.registered_frames}/{report.selected_frames} cameras aligned · scale-free · click actual floor corners in order</p></div><button className="rl-btn" onClick={onClose}>Back to room</button></div>
  <Canvas camera={{position:[10,7,12],fov:50}} raycaster={{params:{Points:{threshold:.10},Mesh:{},Line:{threshold:.1},LOD:{},Sprite:{}}}}>
   <color attach="background" args={['#f5f6f2']}/>
   <points onClick={e=>{e.stopPropagation();if(e.index!=null)onSelect(report.points[e.index].id);}}>
    <bufferGeometry><bufferAttribute attach="attributes-position" args={[data.positions,3]}/><bufferAttribute attach="attributes-color" args={[data.colors,3]}/></bufferGeometry>
    <pointsMaterial size={.055} vertexColors sizeAttenuation/>
   </points>
   {report.cameras.map(c=><mesh key={c.frame_id} position={data.project(c.center)}><sphereGeometry args={[.035,6,6]}/><meshBasicMaterial color="#597b60"/></mesh>)}
   {chosen.length>1&&<Line points={chosen.map(p=>data.project(p.xyz))} color="#b26c39" lineWidth={2}/>}
   {chosen.map((p,i)=><group key={p.id} position={data.project(p.xyz)}><mesh><sphereGeometry args={[.07,8,8]}/><meshBasicMaterial color="#b26c39"/></mesh><Html distanceFactor={12}><span className="rl-point-label">{i+1} · #{p.id}</span></Html></group>)}
   <OrbitControls makeDefault/>
  </Canvas>
  <p className="rl-geometry-cloud-footer">Largest component only · {report.component_count} components · {report.points.length} sparse points · axes and scale are not aligned to your room.</p>
 </div>;
}
