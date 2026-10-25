import test from 'node:test';
import assert from 'node:assert/strict';
import { buildScenarioBrief } from './scenarioBrief.ts';

const context = {geometry_revision:'g1',scenario_revision:2,physical_revision:3,parameters_revision:'p1',solver_version:'s1',state_epoch:'epoch1',context_hash:'hash1'};
const plan = {run_id:'run1',candidate_hash:'candidate1',base_context:context,alternative_id:'KEEP_CURRENT',status:'PARTIAL_WITHIN_HORIZON',initial_population:120,completed_crossings:60,remaining_population:60,horizon_seconds:40,time_step_seconds:2,boundary_breakdown:{B1:60,B2:0},zone_occupancy:{EVENT:60},bottlenecks:[],assumptions:['Declared <capacity>'],validator_report:{is_valid:true,checks_run:['population_conservation'],reasons:[]},provenance:'local'};
const input = {snapshot:{context,current_plan:plan,blocked_portals:['P2'],blocked_boundaries:[],physical_gate_state:'CLOSED'},health:{hardware_mode:'simulator'},grounding:null,capture:null,investigation:null,planCurrent:true,exportedAt:'2026-10-24T06:00:00Z'};

test('portable brief preserves actual counts, context, source and export time without external code',()=>{
 const html=buildScenarioBrief(input);
 for(const text of ['Current checked result at export','60','120','run1','hash1','simulator','2026-10-24T06:00:00Z','Declared &lt;capacity&gt;']) assert.ok(html.includes(text),text);
 assert.equal(/<script\b|<link\b|https?:\/\//i.test(html),false);
 assert.ok(html.includes("default-src 'none'"));
 assert.ok(html.includes('No complete, checked equal-condition comparison'));
});
test('malicious provider text and identifiers are escaped and unsupported images are excluded',()=>{
 const attack='</td><script>alert("x")</script><img src="https://evil.test/x">';
 const html=buildScenarioBrief({...input,grounding:{status:'completed',provenance:'fixture',proposal:{evidence:attack,source_context:context}},capture:{capture_id:attack,source_kind:'fixture',timestamp_iso:'now',dimensions:[600,275],image_base64:'" onerror="alert(1)',source_context:context}});
 assert.ok(html.includes('&lt;script&gt;')); assert.equal(html.includes('<script>'),false);
 assert.equal(html.includes('<img src="https://evil'),false);
 assert.equal(html.includes('src="data:image/jpeg'),false);
});
test('lost connection or stale result stays historical at export even if counts were checked',()=>{
 const html=buildScenarioBrief({...input,planCurrent:false});
 assert.ok(html.includes('Historical or unverified result at export'));
 assert.ok(html.includes('Recorded historical checked numerical result'));
 assert.equal(html.includes('Current checked result at export.'),false);
 const stale=buildScenarioBrief({...input,snapshot:{...input.snapshot,context:{...context,context_hash:'hash2',scenario_revision:3}}});
 assert.ok(stale.includes('Historical or unverified'));
});
test('a failed checker cannot produce a checked count table',()=>{
 const html=buildScenarioBrief({...input,snapshot:{...input.snapshot,current_plan:{...plan,validator_report:{...plan.validator_report,is_valid:false}}}});
 assert.ok(html.includes('No validated population-conserving numerical result'));
 assert.equal(html.includes('Current checked result at export.'),false);
});
test('transit telemetry is not presented as an endpoint receipt or current result',()=>{
 const html=buildScenarioBrief({...input,snapshot:{...input.snapshot,physical_gate_state:'TRANSIT',last_hardware_boot_id:'boot-1',last_gate_epoch:7}});
 assert.ok(html.includes('Hardware telemetry receipt'));
 assert.ok(html.includes('TRANSIT · boot-1 · epoch 7'));
 assert.equal(html.includes('Physical endpoint receipt'),false);
 assert.equal(html.includes('Current checked result at export.'),false);
});
