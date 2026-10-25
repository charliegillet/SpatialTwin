import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { confirmRead, postCalibration, postHazardRead } from '../api/twin.ts';
import { addCorner, calibratedLine, calibrationKey, clearCalibration, clickToImagePoint, confirmedToPlaced, cornersComplete, emptyCorners, errorCopy, isStaleCalibration, loadCalibration, nextCorner, readFailure, saveCalibration, selectFrame, sha256Base64, toCalibrationRequest, undoCorner, usableIds, type CornerState, type ImageSize, type StoredCalibration } from './camera.ts';
import { createReadFlow, idleRead, type ReadState } from './cameraFlow.ts';
import type { HazardReadResponse, PlacedHazard } from './types.ts';

const CAMERA_KEY = 'spatialtwin.cameraId';
const store = (): Storage | null => { try { return window.localStorage; } catch { return null; } };
const message = (error: unknown, fallback: string) => error instanceof Error && error.message ? error.message : fallback;

interface Still { url: string; base64: string; size: ImageSize; }

/** Live camera, sheet calibration, board reads and confirmation for the Camera twin. */
export function useCameraRead({ active, onConfirmed, onProvenance }: { active: boolean; onConfirmed: (hazards: PlacedHazard[]) => number; onProvenance?: (provenance: 'live' | 'fixture') => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [size, setSize] = useState<ImageSize | null>(null);
  const [deviceKey, setDeviceKey] = useState<string>('default');
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState(() => { try { return localStorage.getItem(CAMERA_KEY) ?? ''; } catch { return ''; } });
  const [calibration, setCalibration] = useState<StoredCalibration | null>(null);
  const [calibError, setCalibError] = useState<string | null>(null);
  const [corners, setCorners] = useState<CornerState>(emptyCorners);
  const [calibrating, setCalibrating] = useState(false);
  const [savingCalibration, setSavingCalibration] = useState(false);
  const [still, setStill] = useState<Still | null>(null);
  const [read, setRead] = useState<ReadState<HazardReadResponse>>(idleRead);
  const [confirmedIds, setConfirmedIds] = useState<ReadonlySet<string>>(new Set());
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const generation = useRef(0);
  const stillRef = useRef<Still | null>(null);
  const imageRef = useRef<Still | null>(null);
  const [source, setSource] = useState<'camera' | 'image'>('camera');
  const liveRef = useRef<{ size: ImageSize; deviceKey: string } | null>(null);
  stillRef.current = still;
  const calibrationRef = useRef<StoredCalibration | null>(null);
  calibrationRef.current = calibration;
  const onConfirmedRef = useRef(onConfirmed);
  onConfirmedRef.current = onConfirmed;
  const onProvenanceRef = useRef(onProvenance);
  onProvenanceRef.current = onProvenance;
  const sourceRef = useRef<'camera' | 'image'>('camera');
  sourceRef.current = source;

  const key = size ? calibrationKey(deviceKey, size) : null;

  // Calibration belongs to the camera and its resolution: load it when either is known.
  useEffect(() => { setCalibration(key ? loadCalibration(store(), key) : null); }, [key]);

  // The live stream, only while the Camera twin is open and the live camera is the selected source.
  useEffect(() => {
    if (!active || source !== 'camera') return;
    let cancelled = false;
    let stream: MediaStream | null = null;
    setCameraError(null);
    (async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access needs localhost or a secure connection.');
        const dims = { width: { ideal: 1920 }, height: { ideal: 1080 } };
        const open = (id: string) => navigator.mediaDevices.getUserMedia({ video: id ? { ...dims, deviceId: { exact: id } } : dims, audio: false });
        stream = await open(deviceId).catch(failure => { if (deviceId && failure instanceof DOMException) return open(''); throw failure; });
        if (cancelled) { stream.getTracks().forEach(track => track.stop()); return; }
        const video = videoRef.current;
        if (!video) return;
        video.srcObject = stream;
        await video.play();
        const live = { size: [video.videoWidth, video.videoHeight] as ImageSize, deviceKey: stream.getVideoTracks()[0]?.getSettings().deviceId || 'default' };
        liveRef.current = live;
        if (!imageRef.current) { setSize(live.size); setDeviceKey(live.deviceKey); }
        try { setDevices((await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === 'videoinput')); } catch { setDevices([]); }
      } catch (failure) {
        if (!cancelled) setCameraError(failure instanceof DOMException && failure.name === 'NotAllowedError' ? 'Camera permission was denied.' : message(failure, 'The camera could not be opened.'));
      }
    })();
    return () => { cancelled = true; stream?.getTracks().forEach(track => track.stop()); if (videoRef.current) videoRef.current.srcObject = null; };
  }, [active, deviceId, source]);

  const chooseDevice = (id: string) => { setDeviceId(id); try { if (id) localStorage.setItem(CAMERA_KEY, id); else localStorage.removeItem(CAMERA_KEY); } catch { /* Lasts for this page only. */ } };

  const freeze = useCallback((): Still | null => {
    // The selected source decides: an uploaded image is never replaced by whatever the camera element holds.
    if (sourceRef.current === 'image') return selectFrame('image', null, imageRef.current);
    const video = videoRef.current;
    if (!video || video.readyState < 2 || !video.videoWidth) return null;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) return null;
    context.drawImage(video, 0, 0);
    const url = canvas.toDataURL('image/jpeg', .9);
    return selectFrame<Still>('camera', { url, base64: url.slice(url.indexOf(',') + 1), size: [canvas.width, canvas.height] }, null);
  }, []);

  /** Rehearsal route without a camera: an image of the sheet stands in for the live frame. */
  const useImage = useCallback(async (file: File) => {
    try {
      const bitmap = await createImageBitmap(file);
      const scale = Math.min(1, 1920 / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
      const url = canvas.toDataURL('image/jpeg', .9);
      setSize([canvas.width, canvas.height]); setDeviceKey('image');
      const image = { url, base64: url.slice(url.indexOf(',') + 1), size: [canvas.width, canvas.height] as ImageSize };
      imageRef.current = image; sourceRef.current = 'image'; setStill(image); setSource('image');
      setCameraError(null);
    } catch (failure) { setCalibError(message(failure, 'That image could not be read.')); }
  }, []);

  /** Back to the live camera: the uploaded image is forgotten and the camera's resolution applies again. */
  const useLiveCamera = useCallback(() => {
    imageRef.current = null; sourceRef.current = 'camera'; setSource('camera'); setStill(null);
    setSize(liveRef.current?.size ?? null); setDeviceKey(liveRef.current?.deviceKey ?? 'default');
  }, []);

  const flow = useMemo(() => createReadFlow<HazardReadResponse>({
    run: async signal => {
      const frame = stillRef.current;
      const calib = calibrationRef.current;
      if (!frame) throw new Error('Wait for the camera image.');
      if (!calib) throw new Error(errorCopy('unknown_calibration'));
      return postHazardRead({
        capture_id: crypto.randomUUID(), timestamp_iso: new Date().toISOString(), image_base64: frame.base64,
        image_sha256: await sha256Base64(frame.base64), dimensions: frame.size, calibration_id: calib.calibration_id,
        mode: 'live', thinking_level: 'low', deadline_seconds: 45,
      }, signal);
    },
    onState: setRead,
    describeError: error => message(error, 'The camera read failed.'),
  }), []);
  // Leaving the Camera twin ends every pending confirm: a late response must not repopulate a cleared workspace.
  useEffect(() => () => { generation.current += 1; flow.reset(); }, [flow]);
  useEffect(() => { if (!active) { generation.current += 1; flow.reset(); setStill(null); setCalibrating(false); setConfirmedIds(new Set()); } }, [active, flow]);

  useEffect(() => {
    if (read.phase !== 'reading' || read.startedAt === null) { setElapsed(0); return; }
    const started = read.startedAt;
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(timer);
  }, [read.phase, read.startedAt]);

  const forgetCalibration = useCallback((reason: string) => {
    if (key) clearCalibration(store(), key);
    setCalibration(null); setCalibError(reason);
  }, [key]);

  const beginCalibration = useCallback(() => {
    flow.reset(); generation.current += 1; setConfirmedIds(new Set()); setConfirmError(null);
    const frame = freeze() ?? stillRef.current;
    if (!frame) { setCalibError('Wait for the camera image.'); return; }
    setStill(frame); setCorners(emptyCorners()); setCalibError(null); setCalibrating(true);
  }, [flow, freeze]);

  const clickStill = (event: { clientX: number; clientY: number; currentTarget: Element }) => {
    if (!calibrating || !still) return;
    const point = clickToImagePoint({ x: event.clientX, y: event.clientY }, event.currentTarget.getBoundingClientRect(), still.size);
    setCorners(current => addCorner(current, point, still.size));
  };

  const saveCalibrationNow = async () => {
    if (!still || savingCalibration) return;
    const request = toCalibrationRequest(corners, still.size);
    if (!request) return;
    setSavingCalibration(true); setCalibError(null);
    try {
      const response = await postCalibration(request);
      const next: StoredCalibration = { calibration_id: response.calibration_id, image_size: response.image_size, reprojection_error_m: response.reprojection_error_m };
      setCalibration(next);
      saveCalibration(store(), calibrationKey(deviceKey, still.size), next);
      setCalibrating(false); setStill(null);
    } catch (failure) { setCalibError(message(failure, 'The calibration could not be saved.')); }
    finally { setSavingCalibration(false); }
  };
  const cancelCalibration = () => { setCalibrating(false); setStill(null); setCalibError(null); };

  const readBoard = async () => {
    if (!calibration || !size) return;
    const frame = freeze() ?? stillRef.current;
    if (!frame) { setCalibError('Wait for the camera image.'); return; }
    if (frame.size[0] !== calibration.image_size[0] || frame.size[1] !== calibration.image_size[1]) { forgetCalibration(errorCopy('calibration_image_size_mismatch')); return; }
    generation.current += 1; setConfirmedIds(new Set()); setConfirmError(null); setCalibError(null);
    stillRef.current = frame; setStill(frame);
    await flow.start();
    // A stale calibration reported by the backend is forgotten so the presenter calibrates again.
    const failure = flow.state();
    if (failure.phase === 'error' && failure.error && /expired|resolution changed/i.test(failure.error)) forgetCalibration(failure.error);
  };

  const dismiss = () => { generation.current += 1; flow.reset(); setStill(null); setConfirmedIds(new Set()); setConfirmError(null); };

  const confirm = async (ids: string[]) => {
    const result = read.result;
    if (!result?.read_id || ids.length === 0 || confirming) return;
    const started = generation.current;
    setConfirming(true); setConfirmError(null);
    try {
      const response = await confirmRead(result.read_id, ids);
      if (started !== generation.current) return;
      onConfirmedRef.current(confirmedToPlaced(response));
      if (response.provenance) onProvenanceRef.current?.(response.provenance);
      setConfirmedIds(current => new Set([...current, ...ids]));
    } catch (failure) {
      if (started !== generation.current) return;
      if (isStaleCalibration(failure)) forgetCalibration(errorCopy('unknown_calibration'));
      setConfirmError(message(failure, 'The cards could not be confirmed.'));
    } finally { if (started === generation.current) setConfirming(false); }
  };

  const result = read.result;
  return {
    videoRef, cameraError, size, devices, deviceId, chooseDevice, useImage, useLiveCamera, source,
    calibration, calibError, calibrating, savingCalibration, corners, next: nextCorner(corners), complete: cornersComplete(corners),
    calibratedText: calibration ? calibratedLine() : null,
    beginCalibration, clickStill, undoCorner: () => setCorners(undoCorner), resetCorners: () => setCorners(emptyCorners()), saveCalibrationNow, cancelCalibration,
    still, read, result, readFailureText: result ? readFailure(result) : null, elapsed, readBoard, dismiss,
    confirmedIds, confirm, confirming, confirmError, usable: result ? usableIds(result, confirmedIds) : [],
  };
}
export type CameraRead = ReturnType<typeof useCameraRead>;
