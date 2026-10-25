import { useEffect, useRef, useState } from 'react';
import type { RoomSceneV1 } from './contracts.generated';
import { checkAccuracy, getAccuracy } from './api';

type Check = {element_id:string;dimension:string;measured_value:number;tolerance:number};
type Capture = {selection?:{selected_count?:number;candidate_count?:number;duplicate_skipped_count?:number};tracking?:{status?:string;registered_images?:number};refinement?:{status?:string;additional_frames?:number;message?:string}};
type Results = {independent_length_checks:number;mae_m:number|null;max_error_m:number|null;references:Array<Check & {predicted:number;error:number;fitted_anchor:boolean;within_tolerance:boolean}>};
export function AccuracyPanel({scene,dirty}:{scene:RoomSceneV1|null;dirty:boolean}) {
 const [checks,setChecks]=useState<Check[]>([]),[key,setKey]=useState(''),[measured,setMeasured]=useState(''),[tolerance,setTolerance]=useState('0.02');
 const [report,setReport]=useState<Results|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [capture,setCapture]=useState<Capture|null>(null);
 const epoch=useRef(0);
 useEffect(()=>{const token=++epoch.current;setChecks([]);setReport(null);setCapture(null);setError('');setBusy(false);
  if(scene)void getAccuracy(scene.scene_id).then(r=>{if(token===epoch.current){setReport((r.measurements as Results|null)??null);setCapture((r.capture as Capture|null)??null);}}).catch(()=>{});
  return()=>{epoch.current++};
 },[scene?.scene_id,scene?.scene_revision]);
 if(!scene)return null;
 const options=[...(scene.walls ?? []).map(w=>({id:w.id,dimension:'wall_length',label:`${w.id} · length`})),
  ...(scene.objects ?? []).flatMap(o=>['width','depth','height'].map(d=>({id:o.id,dimension:`object_${d}`,label:`${o.label} · ${d}`}))),
  ...(scene.openings ?? []).map(o=>({id:o.id,dimension:'opening_width',label:`${o.id} · width`}))];
 const add=()=>{const item=options.find(o=>`${o.id}|${o.dimension}`===key);const v=Number(measured),t=Number(tolerance);
  if(!item||!Number.isFinite(v)||v<=0||!Number.isFinite(t)||t<0)return;
  setChecks(old=>[...old.filter(r=>r.element_id!==item.id||r.dimension!==item.dimension),{element_id:item.id,dimension:item.dimension,measured_value:v,tolerance:t}]);setMeasured('');
 };
 const run=async()=>{const token=epoch.current;setBusy(true);setError('');try{const result=await checkAccuracy(scene.scene_id,{expected_revision:scene.scene_revision,references:checks});if(token===epoch.current)setReport(result.measurements as Results);}catch(e){if(token===epoch.current)setError(e instanceof Error?e.message:'Check failed.');}finally{if(token===epoch.current)setBusy(false);}};
 return <section className="rl-panel" aria-label="Independent accuracy checks"><div className="rl-panel-header"><strong>Check actual dimensions</strong></div>
 <p className="rl-muted-note">Enter measurements you took independently. These checks do not change the room; a fitted scale anchor is excluded from accuracy statistics.</p>
 {capture&&<details><summary>Extraction evidence &amp; limits</summary><p className="rl-muted-note">{capture.selection?.selected_count ?? '—'} selected views from {capture.selection?.candidate_count ?? '—'} candidates; {capture.selection?.duplicate_skipped_count ?? 0} duplicates skipped.</p><p className="rl-muted-note">Camera tracking: {capture.tracking?.status ?? 'Unavailable'} · {capture.tracking?.registered_images ?? 0} registered views. Sparse structure is not aligned to the editable room.</p><p className="rl-muted-note">Source reinspection: {capture.refinement?.status ?? 'Unavailable'} · {capture.refinement?.additional_frames ?? 0} additional views. {capture.refinement?.message ?? ''}</p></details>}
 <label className="rl-field">Reference<select aria-label="Measurement reference" value={key} onChange={e=>setKey(e.target.value)}><option value="">Choose a dimension</option>{options.map(o=><option key={`${o.id}|${o.dimension}`} value={`${o.id}|${o.dimension}`}>{o.label}</option>)}</select></label>
 <div className="rl-field-row"><label className="rl-field">Measured (m)<input type="number" step="0.01" min="0.001" value={measured} onChange={e=>setMeasured(e.target.value)}/></label><label className="rl-field">Tolerance (m)<input type="number" step="0.01" min="0" value={tolerance} onChange={e=>setTolerance(e.target.value)}/></label></div>
 <button className="rl-btn" disabled={!key||!(Number(measured)>0)||busy} onClick={add}>Add measured reference</button>
 {checks.map((r,i)=><div key={`${r.element_id}|${r.dimension}`} className="rl-muted-note">{r.element_id} · {r.dimension}: {r.measured_value} m <button aria-label={`Remove check ${i+1}`} onClick={()=>setChecks(old=>old.filter((_,j)=>i!==j))}>×</button></div>)}
 <button className="rl-btn rl-btn--primary" disabled={dirty||busy||!checks.length} onClick={()=>void run()}>{busy?'Checking…':dirty?'Save before checking':'Check measurements'}</button>
 {error&&<p role="alert">{error}</p>}
 {report&&<div aria-live="polite"><p>{report.independent_length_checks} independent checks · mean error {report.mae_m==null?'—':`${report.mae_m.toFixed(3)} m`} · maximum {report.max_error_m==null?'—':`${report.max_error_m.toFixed(3)} m`}</p>{report.references.map(r=><p className="rl-muted-note" key={`${r.element_id}|${r.dimension}`}>{r.element_id}: predicted {r.predicted.toFixed(3)} m, measured {r.measured_value.toFixed(3)} m · {r.fitted_anchor?'Fitted anchor; excluded':r.within_tolerance?'Within tolerance':'Needs review'}</p>)}</div>}
 <p className="rl-muted-note">Results apply only to your supplied references, not the whole room.</p></section>;
}
