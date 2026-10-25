import { useEffect, useRef, useState } from 'react';
import type { GeometryJob,GeometryReport,MediaRecord,RoomSceneV1 } from './contracts.generated';
import {fitGeometryObject,getSavedCapture,getLatestGeometry,analyzeCapture,startGeometry,getGeometry,cancelGeometry,fitGeometryFloor,importRoomPlan,type CaptureQuality} from './api';
export type GeometryPreview={jobId:string;report:GeometryReport};
export function GeometryCapturePanel({media,scene,dirty,selected,preview,onPreview,onSelectPoints,onScene}:{media:MediaRecord|null;scene:RoomSceneV1|null;dirty:boolean;selected:number[];preview:GeometryPreview|null;onPreview:(v:GeometryPreview|null)=>void;onSelectPoints:(v:number[])=>void;onScene:(scene:RoomSceneV1)=>void}) {
 const [job,setJob]=useState<GeometryJob|null>(null),[quality,setQuality]=useState<CaptureQuality|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [measurement,setMeasurement]=useState(''),[height,setHeight]=useState('2.7'),[confirmed,setConfirmed]=useState(false),[topology,setTopology]=useState(false);
 const [objectLabel,setObjectLabel]=useState('Furniture'),[objectCategory,setObjectCategory]=useState('furniture'),[objectConfirmed,setObjectConfirmed]=useState(false);
 const epoch=useRef(0);const upload=useRef<HTMLInputElement>(null);
 useEffect(()=>{const token=++epoch.current;setJob(null);setQuality(null);setError('');setBusy(false);onPreview(null);
  if(media)void Promise.all([getSavedCapture(media.media_id).catch(()=>null),getLatestGeometry(media.media_id).catch(()=>null)]).then(([q,j])=>{if(token===epoch.current){setQuality(q);setJob(j)}});
  return()=>{epoch.current++};
 },[media?.media_id,scene?.scene_id]);
 useEffect(()=>{setConfirmed(false);setTopology(false);setObjectConfirmed(false)},[selected.join(','),measurement]);
 useEffect(()=>{if(!job||!['running','queued'].includes(job.status))return;let stopped=false;let timer:ReturnType<typeof setTimeout>;
  const poll=async()=>{try{const result=await getGeometry(job.job_id);if(!stopped){setJob(result);if(['running','queued'].includes(result.status))timer=setTimeout(()=>void poll(),1800);}}catch(e){if(!stopped){setError(e instanceof Error?e.message:'Status unavailable.');timer=setTimeout(()=>void poll(),4000);}}};
  timer=setTimeout(()=>void poll(),1000);return()=>{stopped=true;clearTimeout(timer)};
 },[job?.job_id,job?.status]);
 const operation=async(fn:()=>Promise<void>)=>{const token=epoch.current;setBusy(true);setError('');try{await fn()}catch(e){if(token===epoch.current)setError(e instanceof Error?e.message:'Operation failed.')}finally{if(token===epoch.current)setBusy(false)}};
 const active=!!job&&['queued','running'].includes(job.status);
 return <section className="rl-panel" aria-label="Geometry and capture evidence"><div className="rl-panel-header"><strong>Geometry &amp; capture evidence</strong></div>
 <p className="rl-muted-note">Inspect selected frames, or recover real camera poses and sparse 3D points on this computer. Sparse geometry is not automatically a complete floor plan.</p>
 {media&&<><div className="rl-video-actions"><button className="rl-btn" disabled={busy||active} onClick={()=>void operation(async()=>{const token=epoch.current;const r=await analyzeCapture(media.media_id);if(token===epoch.current)setQuality(r)})}>{busy?'Working…':'Check footage'}</button>
 <button className="rl-btn" disabled={busy||active} onClick={()=>void operation(async()=>{const token=epoch.current;const r=await startGeometry(media.media_id);if(token===epoch.current)setJob(r)})}>Reconstruct cameras</button></div>
 {quality&&<div className="rl-muted-note">Selected {quality.selected_frame_ids.length} views · {quality.duplicate_skipped_count} duplicates skipped · {quality.low_sharpness_count} low-detail/blur flags · {quality.exposure_flagged_count} exposure flags.<details><summary>Capture notes</summary>{quality.notes.map((n,i)=><p key={i}>{n}</p>)}</details></div>}
 {job&&<p aria-live="polite">Geometry: {job.status}{job.error?` · ${job.error}`:''}</p>}
 {active&&<button className="rl-btn" onClick={()=>void operation(async()=>{setJob(await cancelGeometry(job!.job_id))})}>Cancel reconstruction</button>}
 {job?.report&&<><p className="rl-muted-note">{job.report.registered_frames}/{job.report.selected_frames} views aligned · {job.report.points.length} points · {job.report.mean_reprojection_error_px.toFixed(2)} px reprojection error. This does not measure dimensional accuracy.</p>
 <button className="rl-btn" onClick={()=>onPreview({jobId:job.job_id,report:job.report!})}>Inspect 3D evidence</button></>}
 {preview&&<label className="rl-field">Selected point IDs (perimeter order)<input key={selected.join(",")} defaultValue={selected.join(",")} onBlur={e=>{const ids=e.target.value.split(",").map(v=>v.trim()).filter(v=>/^\d+$/.test(v)).map(Number);onSelectPoints([...new Set(ids)].slice(0,40));}}/><small>Click points in 3D, or paste comma-separated IDs then leave this field. Up to 40.</small></label>}
 {preview&&<details><summary>Build floor from selected landmarks ({selected.length})</summary><p className="rl-muted-note">Click at least three visible floor corners around the perimeter in the 3D evidence view. Avoid stairs and open atriums. The first two points define the edge you measured.</p>
 <p className="rl-muted-note">Point IDs: {selected.join(', ')||'None'}</p><button className="rl-btn" onClick={()=>onPreview({...preview})}>Clear selected corners</button>
 <label className="rl-field">Measured first edge (m)<input type="number" min=".01" step=".01" value={measurement} onChange={e=>setMeasurement(e.target.value)}/></label>
 <label className="rl-field">Estimated wall height (m)<input type="number" min=".1" step=".01" value={height} onChange={e=>setHeight(e.target.value)}/></label>
 <label className="rl-check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I measured the first edge.</label>
 <label className="rl-check"><input type="checkbox" checked={topology} onChange={e=>setTopology(e.target.checked)}/>These floor corners exclude drop-offs and belong to one level.</label>
 <button className="rl-btn" disabled={dirty||busy||!confirmed||!topology||selected.length<3||!(Number(measurement)>0)} onClick={()=>void operation(async()=>{const token=epoch.current;const result=await fitGeometryFloor(preview.jobId,{point_ids:selected,first_edge_measured_m:Number(measurement),wall_height_m:Number(height),measurement_confirmed:confirmed,topology_confirmed:topology});if(token===epoch.current){onScene(result);onPreview(null)}})}>Create separate floor proposal</button><p className="rl-muted-note">Furniture and openings still need review. The original room is preserved.</p></details>}
 {preview&&scene?.geometry_source==='geometry_fit'&&<details><summary>Fit furniture from selected landmarks</summary><p className="rl-muted-note">First create a measured floor from this reconstruction. Select at least four points spanning one object, including its top and sides. Missing surfaces remain uncertain.</p>
 <label className="rl-field">Object label<input value={objectLabel} maxLength={160} onChange={e=>setObjectLabel(e.target.value)}/></label>
 <label className="rl-field">Category<select value={objectCategory} onChange={e=>setObjectCategory(e.target.value)}>{['furniture','table','chair','sofa','counter','plant','stairs'].map(c=><option key={c}>{c}</option>)}</select></label>
 <label className="rl-check"><input type="checkbox" checked={objectConfirmed} onChange={e=>setObjectConfirmed(e.target.checked)}/>These landmarks belong to one floor-supported object.</label>
 <button className="rl-btn" disabled={dirty||busy||!objectConfirmed||selected.length<4||!objectLabel.trim()} onClick={()=>void operation(async()=>{const token=epoch.current;const result=await fitGeometryObject(preview.jobId,{scene_id:scene.scene_id,expected_revision:scene.scene_revision??1,point_ids:selected,label:objectLabel,category:objectCategory,movable:!['stairs','counter'].includes(objectCategory),floor_supported_confirmed:objectConfirmed});if(token===epoch.current){onScene(result);onPreview(null)}})}>Create separate furniture proposal</button></details>}
 </>}
 <input ref={upload} type="file" accept=".json,application/json" hidden onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void operation(async()=>{const token=epoch.current;if(file.size>4*1024*1024)throw new Error('RoomPlan JSON must be at most 4 MiB.');const room=await importRoomPlan(JSON.parse(await file.text()));if(token===epoch.current)onScene(room)});}}/>
 <button className="rl-btn" disabled={dirty||busy} onClick={()=>upload.current?.click()}>Import RoomPlan JSON</button><p className="rl-muted-note">A single CapturedRoom export from a LiDAR iPhone/iPad. JSON only; USDZ, curved walls and multiple floors require conversion.</p>
 {dirty&&<p className="rl-muted-note">Save or undo current room edits before importing a proposal.</p>}{error&&<p role="alert">{error}</p>}
 </section>;
}
