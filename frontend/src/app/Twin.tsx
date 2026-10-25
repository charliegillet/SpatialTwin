import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { api, currentRevision, currentRun } from '../api'
import type { FlowRun, GhostPoint } from '../apiTypes'
import { buildScene } from '../twin/buildScene'
import { counterForStep, doorFlowTotal, formatHero, stepCount } from '../twin/crowdDots'
import { ghostFlashes, ghostPath, latestGeometry, positionAt } from '../twin/ghostWalker'
import { graphToScene } from '../twin/graphToScene'
import { crowdDots, disposeGroup, flashMarkers, flowArrows, ghostBody, ghostTrail, pickTargets } from '../twin/overlays'
import type { VenueGraph } from '../types'
import { fmtT, Tag, useStable, type ScreenProps } from './common'

interface CanvasProps {
  graph: VenueGraph
  hazards: string[]
  run: FlowRun | null
  step: number
  path: GhostPoint[]
  flashes: GhostPoint[]
  videoRef: RefObject<HTMLVideoElement | null>
  onDoor: (id: string) => void
  onFlash: (t: number) => void
}

function TwinCanvas({ graph, hazards, run, step, path, flashes, videoRef, onDoor, onFlash }: CanvasProps) {
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const three = useRef<{ scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls; renderer: THREE.WebGLRenderer } | null>(null)
  const layers = useRef({ crowd: new THREE.Group(), ghost: new THREE.Group(), flashes: new THREE.Group(), picks: new THREE.Group() })
  const ghost = useRef<THREE.Group | null>(null)
  const handlers = useRef({ onDoor, onFlash })
  const pathRef = useRef(path)
  useEffect(() => {
    handlers.current = { onDoor, onFlash }
    pathRef.current = path
  }, [onDoor, onFlash, path])

  const framedFor = useRef<string | null>(null)
  // renderer, camera and the render loop: once
  useEffect(() => {
    framedFor.current = null // a fresh camera needs framing
    const renderer = new THREE.WebGLRenderer({ antialias: true, canvas: canvas.current! })
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio))
    const camera = new THREE.PerspectiveCamera(50, 16 / 9, 0.1, 500)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    const scene = new THREE.Scene()
    three.current = { scene, camera, controls, renderer }
    // keep the drawing buffer and the camera in step with the element's size (checked every frame)
    const size = new THREE.Vector2()
    const fit = () => {
      const el = wrap.current
      if (!el) return
      const w = el.clientWidth, h = el.clientHeight
      renderer.getSize(size)
      if (w && h && (size.x !== w || size.y !== h)) {
        renderer.setSize(w, h, false)
        camera.aspect = w / h
        camera.updateProjectionMatrix()
      }
    }
    let raf = 0
    const tick = () => {
      raf = requestAnimationFrame(tick)
      fit()
      const t = videoRef.current?.currentTime ?? 0
      const p = positionAt(pathRef.current, t)
      if (ghost.current) {
        ghost.current.visible = !!p
        if (p) ghost.current.position.copy(graphToScene(p.x, p.y))
      }
      for (const m of layers.current.flashes.children as THREE.Mesh[]) {
        const near = Math.abs(t - (m.userData.t_s as number)) < 1.2
        const mat = m.material as THREE.MeshStandardMaterial
        mat.emissiveIntensity = near ? 1.5 + Math.sin(performance.now() / 60) : 0.4
        m.scale.setScalar(near ? 1.6 : 1)
      }
      controls.update()
      renderer.render(three.current!.scene, camera)
    }
    tick()
    // click picking (ignore orbit drags)
    let down: [number, number] | null = null
    const el = renderer.domElement
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY] }
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6) return
      const r = el.getBoundingClientRect()
      const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      const ray = new THREE.Raycaster()
      ray.setFromCamera(ndc, camera)
      const hits = ray.intersectObjects([...layers.current.flashes.children, ...layers.current.picks.children], false)
      const hit = hits[0]?.object
      if (!hit) return
      if (hit.name.startsWith('flash:')) handlers.current.onFlash(hit.userData.t_s as number)
      else if (hit.name.startsWith('pick:')) handlers.current.onDoor(hit.name.slice(5))
    }
    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    return () => {
      cancelAnimationFrame(raf)
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointerup', onUp)
      controls.dispose()
      renderer.dispose()
    }
  }, [videoRef])

  // base twin: rebuilt when the graph or hazards change
  useEffect(() => {
    const t = three.current!
    const scene = buildScene(graph, { hazards })
    scene.background = new THREE.Color(0x0e1116)
    const L = layers.current
    disposeGroup(L.picks)
    L.picks.add(pickTargets(graph))
    scene.add(L.crowd, L.ghost, L.flashes, L.picks)
    const old = t.scene
    t.scene = scene
    disposeGroup(old) // overlay layers were already re-parented onto the new scene
    // frame the camera once per venue
    const key = graph.zones.map((z) => z.rect.join(',')).join(';')
    if (framedFor.current !== key && graph.zones.length) {
      framedFor.current = key
      const xs = graph.zones.flatMap((z) => [z.rect[0], z.rect[0] + z.rect[2]])
      const ys = graph.zones.flatMap((z) => [z.rect[1], z.rect[1] + z.rect[3]])
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2
      const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys))
      const target = graphToScene(cx, cy)
      t.controls.target.copy(target)
      const el = wrap.current
      const aspect = el && el.clientHeight ? el.clientWidth / el.clientHeight : 16 / 9
      const back = Math.max(1, 1.2 / aspect) // portrait phones need to stand further back
      t.camera.position.copy(graphToScene(cx, cy - span * 0.75 * back, span * 0.85 * back))
      t.camera.lookAt(target)
    }
  }, [graph, hazards])

  // crowd dots and door-flow arrows for step k
  useEffect(() => {
    const g = layers.current.crowd
    disposeGroup(g)
    if (run) g.add(crowdDots(graph, run, step), flowArrows(graph, run, step))
  }, [graph, run, step])

  // ghost walker and flashes
  useEffect(() => {
    const L = layers.current
    disposeGroup(L.ghost)
    disposeGroup(L.flashes)
    ghost.current = null
    if (path.length > 1) {
      L.ghost.add(ghostTrail(path))
      ghost.current = ghostBody()
      L.ghost.add(ghost.current)
    }
    L.flashes.add(...flashMarkers(flashes).children)
  }, [path, flashes])

  return <div className="twin-canvas" ref={wrap}><canvas ref={canvas} aria-label="3D twin. Click a door to drop fire on it, click a red flash to see that moment in the video." /></div>
}

export function Twin({ snap, act, pending, seek, videoRef }: ScreenProps & { videoRef: RefObject<HTMLVideoElement | null> }) {
  const rev = currentRevision(snap)
  const graph = useStable(snap.accepted_graph, JSON.stringify(snap.accepted_graph))
  const live = currentRun(snap)
  const run = useStable(live, live?.run_id ?? '')
  const check = snap.current_check
  const hazardKey = snap.scenario.hazards.map((h) => h.door_id).join(',')
  const hazards = useMemo(() => (hazardKey ? hazardKey.split(',') : []), [hazardKey])
  const rawPath = ghostPath(snap)
  const path = useStable(rawPath, JSON.stringify(rawPath))
  const geo = latestGeometry(snap)
  const rawFlashes = geo ? ghostFlashes(geo) : []
  const flashes = useStable(rawFlashes, JSON.stringify(rawFlashes))
  const resolving = pending === 'Changing the hazard'
  const shownRun = resolving ? null : run
  const K = shownRun ? stepCount(shownRun) - 1 : 0
  const [step, setStep] = useState(K)
  const [playing, setPlaying] = useState(false)
  useEffect(() => { setStep(K); setPlaying(false) }, [shownRun?.run_id, K])
  useEffect(() => {
    if (!playing) return
    const t = setInterval(() => setStep((k) => { if (k >= K) { setPlaying(false); return K } return k + 1 }), 200)
    return () => clearInterval(t)
  }, [playing, K])

  if (!graph) return <section className="screen"><div className="panel"><p className="muted">Accept the twin in Review to load it here.</p></div></section>

  const toggleFire = (doorId: string) => {
    if (!rev || pending) return
    const next = hazards.includes(doorId) ? hazards.filter((h) => h !== doorId) : [...hazards, doorId]
    void act('Changing the hazard', () => api.setHazards(snap.id, rev, next.map((door_id) => ({ door_id, kind: 'fire' as const, from_s: 0 }))))
  }
  const c = shownRun ? counterForStep(shownRun, step) : null
  const checked = !!(shownRun && check && check.ok && check.run_id === shownRun.run_id)
  const exits = graph.doors.filter((d) => d.kind === 'exit' || d.b === 'OUTSIDE')
  const others = graph.doors.filter((d) => !exits.includes(d))

  return (
    <section className="screen twin">
      <div className="hero" aria-live="polite">
        {shownRun ? (
          <>
            <p className="hero-number">{formatHero(shownRun.reached_exit, shownRun.total, shownRun.params.horizon_s)}{checked ? ' · checked' : ''}</p>
            {checked ? <Tag kind="checked">checker verified</Tag> : <Tag kind="error">{check && !check.ok ? `checker found ${check.violations.length} violations` : 'not checked'}</Tag>}
            {hazards.length > 0 && <span className="muted"> Fire on {hazards.join(', ')}</span>}
          </>
        ) : <p className="hero-number muted">{resolving ? 'Re-solving for the new hazard…' : 'No current run for this revision.'}</p>}
      </div>
      <TwinCanvas graph={graph} hazards={hazards} run={shownRun} step={step} path={path} flashes={flashes}
        videoRef={videoRef} onDoor={toggleFire} onFlash={seek} />
      <div className="twin-controls panel">
        {shownRun && c && (
          <div className="stepper">
            <button onClick={() => { if (step >= K) setStep(0); setPlaying((p) => !p) }}>{playing ? 'Pause' : 'Play crowd'}</button>
            <input type="range" min={0} max={K} value={step} onChange={(e) => { setPlaying(false); setStep(Number(e.target.value)) }} aria-label="Solver step" />
            <p className="counter">
              t = {c.t_s} s · <strong>{c.inZones}</strong> in rooms + <strong>{c.inTransit}</strong> moving + <strong>{c.reached}</strong> at exits = {c.total}
              {step === K && c.reached === shownRun.reached_exit && <span className="reconciled"> · matches the headline</span>}
            </p>
            <p className="muted">One dot per person, from the solver's zone occupancy. Arrow thickness = people through that door this step.</p>
          </div>
        )}
        <div className="fire">
          <h3>Drop fire</h3>
          <p className="muted">Click a door in the twin, or pick one here.</p>
          <div className="chips">
            {[...exits, ...others].map((d) => (
              <button key={d.id} className={`chip${hazards.includes(d.id) ? ' on' : ''}`} disabled={!!pending} onClick={() => toggleFire(d.id)}
                aria-pressed={hazards.includes(d.id)}>
                {hazards.includes(d.id) ? 'Fire: ' : ''}{d.id} {d.kind === 'exit' || d.b === 'OUTSIDE' ? 'exit' : d.kind}
                {shownRun && <span className="chip-sub"> · {doorFlowTotal(shownRun, d.id)} through</span>}
              </button>
            ))}
          </div>
        </div>
        <div className="ghost-ctl">
          <h3>Your walk</h3>
          {path.length > 1 ? (
            <>
              <button onClick={() => { const v = videoRef.current; if (v) { if (v.paused) void v.play(); else v.pause() } }}>Play / pause walk</button>
              <span className="muted"> The ghost follows the video clock along your SfM path.</span>
              {flashes.length > 0 ? (
                <div className="chips">
                  {flashes.map((f, i) => (
                    <button key={i} className="chip flash-chip" onClick={() => seek(f.t_s)}>Wall crossing {fmtT(f.t_s)}</button>
                  ))}
                </div>
              ) : <p className="muted">No illegal crossings measured.</p>}
            </>
          ) : <p className="muted">No SfM path for this session.</p>}
        </div>
        {shownRun && (
          <p className="declared"><Tag kind="declared">declared</Tag> dt {shownRun.params.dt_s} s · horizon {shownRun.params.horizon_s} s · {shownRun.params.specific_flow_p_per_m_s} p/m/s on effective width (minus {shownRun.params.boundary_layer_m} m each side) · walk {shownRun.params.walk_speed_m_s} m/s</p>
        )}
      </div>
    </section>
  )
}
