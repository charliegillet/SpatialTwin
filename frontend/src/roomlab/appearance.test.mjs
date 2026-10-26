import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { buildObjectVisualParts, buildOpeningVisualParts, classifyVisualCategory } from './visualBounds.ts';
import { createPartGeometry, setPiecePicking, shellOutwardNormal } from './visualGeometry.ts';
import { wallFrameParts } from './wallVisualParts.ts';
import { resolveFloorAppearance, resolveAppearance, resolveWallAppearance, materialHint } from './appearance.ts';

test('actual proxy vertices stay inside canonical OBB with unequal tiny dimensions and parent yaw',()=>{
  for(const category of ['plant','stool','sofa','bed','shelf','appliance','tv','counter','table','chair','bicycle','stairs','door_leaf','stand','pillar','bin','custom'])
  for(const [w,h,d] of [[.011,.007,.003],[.003,.007,.011],[1.2,.8,2.4],[2.4,.8,1.2],[1.6,3.2,2.8],[3.2,3.2,1.6],[.4,3.2,.8],[.8,.8,.8]])
  for(const mode of ['proxy','bounds'])
  for(const yaw of [0,Math.PI/6,Math.PI/2]) {
    const group=new THREE.Group();group.position.set(2,0,-3);group.rotation.y=yaw;
    const meshes=buildObjectVisualParts(w,h,d,category,'',mode).map(p=>{const m=new THREE.Mesh(createPartGeometry(p));m.position.set(...p.position);group.add(m);return m;});
    group.updateMatrixWorld(true);const inverse=group.matrixWorld.clone().invert();
    for(const m of meshes) {const a=m.geometry.getAttribute('position');for(let i=0;i<a.count;i++){const v=new THREE.Vector3().fromBufferAttribute(a,i).applyMatrix4(m.matrixWorld).applyMatrix4(inverse);assert.ok(Math.abs(v.x)<=w/2+1e-6 && Math.abs(v.z)<=d/2+1e-6 && v.y>=-1e-6 && v.y<=h+1e-6,`${category}: ${[w,h,d]} ${v.toArray()}`);}m.geometry.dispose();}
  }
  assert.equal(classifyVisualCategory('plant','Potted Plant (Near Stairs)'),'plant');
  assert.equal(buildObjectVisualParts(.4,.5,.4,'stool','Wooden stool').filter(p=>p.id.includes('seat')).length,1);
});

test('short glass frames and apertures keep every actual vertex within bounds',()=>{
  for(const [w,h,d] of [[.003,.007,.001],[.1,.04,.02],[2.1,2.4,.12]]) {
    const lists=[{parts:wallFrameParts(w,h,d),min:-h/2,max:h/2},...['door','window','passage'].map(kind=>({parts:buildOpeningVisualParts(kind,w,h,.2,d),min:.2,max:.2+h}))];
    for(const {parts,min,max} of lists)for(const p of parts){const g=createPartGeometry(p);g.translate(...p.position);g.computeBoundingBox();const b=g.boundingBox;assert.ok(b.min.x>=-w/2-1e-6 && b.max.x<=w/2+1e-6 && b.min.z>=-d/2-1e-6 && b.max.z<=d/2+1e-6 && b.min.y>=min-1e-6 && b.max.y<=max+1e-6);g.dispose();}
  }
});

test('hidden wall picking is off, visible curb and restored wall retain original raycast',()=>{
  const m=new THREE.Mesh(new THREE.BoxGeometry(1,1,1));m.updateMatrixWorld(true);
  const ray=new THREE.Raycaster(new THREE.Vector3(0,0,3),new THREE.Vector3(0,0,-1));const original=m.raycast;
  assert.ok(ray.intersectObject(m).length>0);
  setPiecePicking(m,false,original);assert.equal(ray.intersectObject(m).length,0);
  setPiecePicking(m,true,original);m.scale.y=.1;m.updateMatrixWorld(true);assert.ok(ray.intersectObject(m).length>0);assert.equal(m.raycast,original);m.geometry.dispose();
});

test('concave shell outward normal is stable for matching CW and CCW edges',()=>{
  const floor=[[0,0],[6,0],[6,1],[1,1],[1,6],[0,6]];
  assert.deepEqual(shellOutwardNormal(floor,[6,1],[1,1]),[0,1]);
  const normal=shellOutwardNormal([...floor].reverse(),[1,1],[6,1]);assert.ok(Math.abs(normal[0])<1e-8);assert.equal(normal[1],1);
  for(const points of [floor,[...floor].reverse()])for(let i=0;i<points.length;i++){const n=shellOutwardNormal(points,points[i],points[(i+1)%points.length]);assert.ok(Math.abs(Math.hypot(...n)-1)<1e-8);}
});

test('floor finish guesses stay scoped and conservative, user choices win',()=>{
  assert.equal(resolveFloorAppearance({notes:['Marble counter and wooden stools.'],floor:[]}).material,'unknown');
  assert.equal(resolveFloorAppearance({notes:['Floor material: terrazzo.'],floor:[]}).material,'terrazzo');
  assert.equal(resolveFloorAppearance({notes:['Floor is not wood.'],floor:[]}).material,'unknown');
  assert.equal(resolveFloorAppearance({notes:['Floor is mixed wood and stone.'],floor:[]}).material,'unknown');
  assert.equal(materialHint('Wooden stool'),'wood');
  const appearance={color:'#aaaaaa',material:'marble',provenance:{source:'model_estimate',evidence_frame_ids:['f1']},user_override:{color:'#eeeeee',material:'wood'}};
  assert.equal(resolveAppearance(appearance).source,'user_choice');assert.equal(resolveAppearance(appearance).material,'wood');
});

test('appearance priority preserves individual user choices above default shell color',()=>{
 const base={color:'#cccccc',material:'paint',provenance:{source:'model_estimate'}};
 const global={...base,user_override:{color:'#ffeecc',material:'paint'}};
 assert.equal(resolveWallAppearance({role:'shell',appearance:base},global).color,'#ffeecc');
 assert.equal(resolveWallAppearance({role:'shell',appearance:{...base,user_override:{color:'#aabbcc',material:'paint'}}},global).color,'#aabbcc');
 assert.equal(resolveWallAppearance({role:'partition',appearance:{...base,material:'glass'}},global).material,'glass');
 assert.equal(resolveFloorAppearance({notes:['Floor is wood in the kitchen.']}).material,'unknown');
 assert.equal(resolveFloorAppearance({notes:['Floor is not wood.','Floor is terrazzo.']}).material,'unknown');
});

test('stair proxy ascends away from frontage for depth-axis yaw +90 and handrail is sloped',()=>{
 const parts=buildObjectVisualParts(1.6,3.2,2.8,'stairs','Interior Staircase');
 const steps=parts.filter(p=>p.id.startsWith('stair-step-'));
 const first=new THREE.Vector3(...steps[0].position).applyAxisAngle(new THREE.Vector3(0,1,0),Math.PI/2);
 const last=new THREE.Vector3(...steps.at(-1).position).applyAxisAngle(new THREE.Vector3(0,1,0),Math.PI/2);
 assert.ok(last.x>first.x && last.y>first.y);
 const rail=parts.find(p=>p.id==='stair-sloped-rail');assert.ok(rail.rotation[0]<0);
 const g=createPartGeometry(rail);g.computeBoundingBox();assert.ok(g.boundingBox.max.y-g.boundingBox.min.y>1);g.dispose();
 const sofa=buildObjectVisualParts(2.2,.8,.95,'sofa','Lounge Sofa');assert.ok(sofa.find(p=>p.id==='sofa-back').position[2]<0);
});
