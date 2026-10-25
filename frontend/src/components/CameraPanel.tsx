import { useEffect, useRef } from 'react';
import { Camera, Check, LoaderCircle, Ruler, ScanSearch, Undo2, X } from 'lucide-react';
import { CORNER_ORDER, SOURCE_LABEL, chipView } from '../twin/camera';
import { useCameraRead } from '../twin/useCameraRead';
import type { PlacedHazard, VenueV2 } from '../twin/types';

interface Props {
  venue: VenueV2;
  onConfirmed: (hazards: PlacedHazard[]) => number;
  /** Bumped by the presenter menu's Calibrate sheet action. */
  calibrateTick: number;
  /** Rehearsal source chosen in the presenter menu; null means the live camera. */
  imageFile: File | null;
  /** Provenance of a confirmed read, so the badge is right before the plan arrives. */
  onProvenance?: (provenance: 'live' | 'fixture') => void;
}

/** Live camera over the printed sheet: calibrate once, read the board, confirm the cards. Perception only; nothing physical moves. */
export function CameraPanel({ venue, onConfirmed, calibrateTick, imageFile, onProvenance }: Props) {
  const cam = useCameraRead({ active: true, onConfirmed, onProvenance });
  const lastTick = useRef(calibrateTick);
  useEffect(() => { if (calibrateTick !== lastTick.current) { lastTick.current = calibrateTick; cam.beginCalibration(); } });
  const { useImage, useLiveCamera } = cam;
  useEffect(() => { if (imageFile) void useImage(imageFile); else useLiveCamera(); }, [imageFile, useImage, useLiveCamera]);
  const reading = cam.read.phase === 'reading';
  const result = cam.result;
  const chips = result ? result.candidates.map(item => ({ item, view: chipView(item, result, venue, cam.confirmedIds, cam.source) })) : [];
  const frozen = Boolean(cam.still);
  const [w, h] = cam.still?.size ?? [16, 9];
  const instruction = cam.calibrating ? (cam.next ? `Click corner ${cam.next} (${CORNER_ORDER.indexOf(cam.next) + 1} of 4)` : 'All four corners set') : null;

  return <section className="camera-panel hazard-palette" aria-label="Camera">
    <header className="camera-head">
      <h3>Camera</h3>
      <span className="camera-tags">
        <span className={`chip ${cam.source === 'image' ? 'chip-pending' : 'chip-info'}`}>{SOURCE_LABEL[cam.source]}</span>
        <span className={`chip ${cam.calibration ? 'chip-ok' : 'chip-warn'}`}>{cam.calibratedText ?? 'Not calibrated'}</span>
      </span>
    </header>
    <div className={`camera-frame${cam.calibrating ? ' is-calibrating' : ''}`} style={{ aspectRatio: `${w} / ${h}` }}>
      <video ref={cam.videoRef} muted playsInline aria-label="Live camera" hidden={frozen || Boolean(cam.cameraError)} />
      {cam.cameraError && !frozen && <p className="camera-error" role="alert">{cam.cameraError}</p>}
      {frozen && cam.still && <div className="camera-still" onClick={cam.clickStill} role={cam.calibrating ? 'application' : 'img'} aria-label={cam.calibrating ? 'Frozen frame. Click the corner markers in order.' : 'Frozen frame of the board'}>
        <img src={cam.still.url} alt="" draggable={false} />
        {cam.calibrating && cam.corners.points.map(([x, y], index) => <i key={index} className="camera-dot" style={{ left: `${(x / w) * 100}%`, top: `${(y / h) * 100}%` }}>{CORNER_ORDER[index]}</i>)}
        {!cam.calibrating && chips.map(({ item, view }) => <i key={item.candidate_id} className={`camera-box camera-box-${view.tone}`} style={{ left: `${view.box.left}%`, top: `${view.box.top}%`, width: `${view.box.width}%`, height: `${view.box.height}%` }} />)}
        {reading && <span className="camera-reading"><LoaderCircle size={14} className="spin" aria-hidden="true" />Reading · {cam.elapsed} s</span>}
      </div>}
    </div>

    {instruction && <p className="hazard-hint" role="status">{instruction}</p>}
    {cam.calibError && <p className="hazard-notice" role="alert">{cam.calibError}</p>}
    {cam.devices.length > 1 && !frozen && <label className="board-device"><span>Camera</span><select aria-label="Camera device" value={cam.devices.some(device => device.deviceId === cam.deviceId) ? cam.deviceId : ''} onChange={event => cam.chooseDevice(event.target.value)}><option value="">Default camera</option>{cam.devices.map((device, index) => <option key={device.deviceId || index} value={device.deviceId}>{device.label || `Camera ${index + 1}`}</option>)}</select></label>}

    {cam.calibrating ? <div className="twin-actions">
      <button type="button" className="btn" onClick={cam.undoCorner} disabled={cam.corners.points.length === 0}><Undo2 size={14} aria-hidden="true" />Undo</button>
      <button type="button" className="btn" onClick={cam.resetCorners} disabled={cam.corners.points.length === 0}>Reset</button>
      <button type="button" className="btn btn-primary" onClick={() => void cam.saveCalibrationNow()} disabled={!cam.complete || cam.savingCalibration}>{cam.savingCalibration ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}Save</button>
      <button type="button" className="btn btn-icon" onClick={cam.cancelCalibration} aria-label="Cancel calibration"><X size={14} aria-hidden="true" /></button>
    </div> : <div className="twin-actions">
      <button type="button" className="btn" onClick={cam.beginCalibration} disabled={reading || (!cam.size && !cam.still)}><Ruler size={14} aria-hidden="true" />{cam.calibration ? 'Recalibrate' : 'Calibrate sheet'}</button>
      <button type="button" className="btn btn-primary" onClick={() => void cam.readBoard()} disabled={!cam.calibration || reading || !cam.size}><ScanSearch size={14} aria-hidden="true" />Read the board</button>
    </div>}
    {!cam.calibration && !cam.calibrating && !cam.calibError && <p className="hazard-hint">Calibrate once: click the sheet's four corner markers.</p>}

    {cam.read.phase === 'error' && cam.read.error !== cam.calibError && <p className="hazard-notice" role="alert">{cam.read.error}</p>}
    {result && cam.readFailureText && <p className="hazard-notice" role="alert">{cam.readFailureText}<small> · {result.provenance === 'unavailable' ? 'Unavailable' : result.status.replace(/_/g, ' ')}</small></p>}
    {result && !cam.readFailureText && <>
      {chips.length === 0 && <p className="twin-quiet">No red cards found.</p>}
      <ul className="camera-chips" aria-label="Cards read from the board">
        {chips.map(({ item, view }) => <li key={item.candidate_id} className={`camera-chip camera-chip-${view.tone}`}>
          <span className="camera-chip-label">{view.label}</span>
          {view.note && <small>{view.note}</small>}
          {view.confirmed ? <span className="chip chip-ok"><Check size={12} aria-hidden="true" />Confirmed</span>
            : <button type="button" className="btn btn-quiet" disabled={!view.usable || cam.confirming} onClick={() => void cam.confirm([item.candidate_id])}>Confirm</button>}
        </li>)}
      </ul>
      {cam.confirmError && <p className="hazard-notice" role="alert">{cam.confirmError}</p>}
      <p className="twin-quiet">{result.mapping_note}</p>
    </>}
    {(result || cam.read.phase === 'error') && <div className="twin-actions">
      {cam.usable.length > 1 && <button type="button" className="btn btn-primary" disabled={cam.confirming} onClick={() => void cam.confirm(cam.usable)}>Confirm all usable</button>}
      <button type="button" className="btn" onClick={cam.dismiss}><X size={14} aria-hidden="true" />Dismiss</button>
    </div>}
    <p className="twin-quiet camera-foot"><Camera size={12} aria-hidden="true" /> Perception only. The door plan stays a local solver; nothing physical moves.</p>
  </section>;
}
