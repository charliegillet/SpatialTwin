import React, { useState, useEffect, useRef } from 'react';
import {
  Camera,
  Video,
  VideoOff,
  Maximize2,
  Sliders,
  Sparkles,
  Layers,
  RefreshCw,
  Eye,
  CheckCircle2,
} from 'lucide-react';
import { GroundingProposalV1 } from '../types';
import { sounds } from '../utils/audio';

interface CameraFeedPanelProps {
  onCaptureFrame: (imageBase64?: string, targetOverride?: string, thinkingLevel?: 'low' | 'medium' | 'high') => Promise<GroundingProposalV1>;
  proposal: GroundingProposalV1 | null;
  thinkingLevel: 'low' | 'medium' | 'high';
  setThinkingLevel: (level: 'low' | 'medium' | 'high') => void;
  onApplyProposal: () => Promise<void>;
  isGroundingLoading: boolean;
}

export const CameraFeedPanel: React.FC<CameraFeedPanelProps> = ({
  onCaptureFrame,
  proposal,
  thinkingLevel,
  setThinkingLevel,
  onApplyProposal,
  isGroundingLoading,
}) => {
  const [feedSource, setFeedSource] = useState<'tabletop_fixture' | 'live_webcam'>('tabletop_fixture');
  const [videoDevices, setVideoDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [isCameraActive, setIsCameraActive] = useState<boolean>(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Enumerate cameras
  const enumerateCameras = async () => {
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoInputs = devices.filter((d) => d.kind === 'videoinput');
        setVideoDevices(videoInputs);
        if (videoInputs.length > 0 && !selectedDeviceId) {
          setSelectedDeviceId(videoInputs[0].deviceId);
        }
      }
    } catch (e) {
      console.warn('Camera device enumeration failed:', e);
    }
  };

  const startWebcam = async (deviceId?: string) => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      const constraints: MediaStreamConstraints = {
        video: deviceId
          ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
          : { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsCameraActive(true);
      await enumerateCameras();
    } catch (err) {
      console.warn('Webcam stream unavailable:', err);
      setIsCameraActive(false);
    }
  };

  const stopWebcam = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
  };

  useEffect(() => {
    if (feedSource === 'live_webcam') {
      startWebcam(selectedDeviceId);
    } else {
      stopWebcam();
    }
    return () => {
      stopWebcam();
    };
  }, [feedSource, selectedDeviceId]);

  // Handle Capture Action
  const handleTriggerDetection = async (targetOverride?: string) => {
    sounds.playGroundingPing();

    let imageBase64: string | undefined = undefined;
    if (feedSource === 'live_webcam' && videoRef.current && canvasRef.current && isCameraActive) {
      const v = videoRef.current;
      const c = canvasRef.current;
      c.width = v.videoWidth || 1280;
      c.height = v.videoHeight || 720;
      const ctx = c.getContext('2d');
      if (ctx) {
        ctx.drawImage(v, 0, 0, c.width, c.height);
        imageBase64 = c.toDataURL('image/jpeg', 0.85).split(',')[1];
      }
    }

    await onCaptureFrame(imageBase64, targetOverride, thinkingLevel);
  };

  return (
    <div className="relative w-full h-[410px] bg-slate-950/95 rounded-xl border border-slate-800/90 flex flex-col justify-between overflow-hidden shadow-2xl">
      {/* Top Header matching reference photo */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-900/80 border-b border-slate-800 text-xs">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          <span className="font-bold text-slate-200 uppercase font-mono tracking-wide">Camera 1</span>
          <span className="text-slate-500">•</span>
          <span className="text-[11px] text-cyan-400 font-mono">
            {feedSource === 'live_webcam' ? 'Live Tabletop Cam' : 'Physical Rig (Hand & Red Cube)'}
          </span>
        </div>

        {/* Source Toggle */}
        <div className="flex items-center space-x-1.5 text-[11px]">
          <div className="inline-flex rounded bg-slate-950 border border-slate-800 p-0.5">
            <button
              onClick={() => setFeedSource('tabletop_fixture')}
              className={`px-2 py-0.5 rounded transition ${
                feedSource === 'tabletop_fixture'
                  ? 'bg-cyan-600 text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Tabletop Demo
            </button>
            <button
              onClick={() => setFeedSource('live_webcam')}
              className={`px-2 py-0.5 rounded transition ${
                feedSource === 'live_webcam'
                  ? 'bg-cyan-600 text-white font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              USB Webcam
            </button>
          </div>
        </div>
      </div>

      {/* Main Video Viewport */}
      <div className="relative flex-1 bg-black flex items-center justify-center overflow-hidden">
        {feedSource === 'tabletop_fixture' ? (
          /* Tabletop Reference View matching user screenshot (Hand holding red hazard cube) */
          <div className="relative w-full h-full bg-[#0d121f] flex items-center justify-center overflow-hidden select-none">
            {/* Background tabletop grid / table surface */}
            <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:20px_20px] opacity-40"></div>

            {/* Simulated Tabletop Rig Photo Visual */}
            <div className="relative w-full h-full flex items-center justify-center">
              {/* Tabletop Foam Board Maze Model in background */}
              <svg viewBox="0 0 400 240" className="w-full h-full opacity-80">
                {/* Board base */}
                <path d="M 50 180 L 350 180 L 380 70 L 80 70 Z" fill="#1e293b" stroke="#334155" strokeWidth="2" />
                {/* Corridors and walls */}
                <path d="M 120 160 L 120 90 L 160 90 L 160 160" fill="none" stroke="#64748b" strokeWidth="4" />
                <path d="M 240 160 L 240 90 L 280 90 L 280 160" fill="none" stroke="#64748b" strokeWidth="4" />
                <path d="M 160 125 L 240 125" fill="none" stroke="#64748b" strokeWidth="4" />
              </svg>

              {/* Hand Holding 3D Red Cube (Isometric Block) */}
              <div className="absolute top-8 left-12 transform hover:scale-105 transition-transform duration-300">
                {/* Hand outline */}
                <div className="relative">
                  <svg width="180" height="150" viewBox="0 0 180 150">
                    {/* Hand skin tone fingers */}
                    <path
                      d="M 10 90 Q 30 50 60 40 Q 90 35 110 50 Q 120 70 125 90 Q 90 100 40 110 Z"
                      fill="#e2a178"
                      stroke="#c88358"
                      strokeWidth="2"
                    />
                    {/* Thumb */}
                    <path
                      d="M 25 80 Q 55 90 75 105 Q 60 120 30 115 Z"
                      fill="#d9946c"
                      stroke="#b87248"
                      strokeWidth="2"
                    />
                  </svg>

                  {/* 3D Red Hazard Block / Cube */}
                  <div className="absolute top-6 left-16">
                    <svg width="86" height="86" viewBox="0 0 100 100" className="drop-shadow-2xl">
                      {/* Top Face */}
                      <polygon points="50,10 90,30 50,50 10,30" fill="#f87171" stroke="#dc2626" strokeWidth="1.5" />
                      {/* Right Face */}
                      <polygon points="50,50 90,30 90,75 50,95" fill="#dc2626" stroke="#b91c1c" strokeWidth="1.5" />
                      {/* Left Face */}
                      <polygon points="10,30 50,50 50,95 10,75" fill="#ef4444" stroke="#b91c1c" strokeWidth="1.5" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Spatial Bounding Box from Argon on Red Hazard Cube */}
              <div className="absolute top-10 left-20 w-32 h-28 border-2 border-rose-500 bg-rose-500/20 rounded shadow-[0_0_15px_rgba(244,63,94,0.6)] flex items-start justify-end p-1 animate-pulse">
                <span className="text-[10px] font-mono font-bold bg-rose-600 text-white px-1.5 py-0.5 rounded shadow">
                  portal:P2 (HAZARD CUBE)
                </span>
              </div>
            </div>
          </div>
        ) : (
          /* Live Webcam Stream */
          <div className="relative w-full h-full flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover ${!isCameraActive ? 'hidden' : ''}`}
            />
            {!isCameraActive && (
              <div className="flex flex-col items-center justify-center space-y-2 text-slate-500 text-xs">
                <VideoOff className="h-8 w-8 text-slate-600" />
                <span>Webcam initializing or permission requested</span>
                <button
                  onClick={() => startWebcam(selectedDeviceId)}
                  className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-cyan-400 rounded text-xs border border-slate-700 font-semibold"
                >
                  Start Webcam
                </button>
              </div>
            )}
            <canvas ref={canvasRef} style={{ display: 'none' }} />

            {/* AR Bounding Box on live webcam if returned */}
            {proposal?.box_2d && (
              <div
                style={{
                  position: 'absolute',
                  top: `${proposal.box_2d[0] / 10}%`,
                  left: `${proposal.box_2d[1] / 10}%`,
                  height: `${(proposal.box_2d[2] - proposal.box_2d[0]) / 10}%`,
                  width: `${(proposal.box_2d[3] - proposal.box_2d[1]) / 10}%`,
                }}
                className="border-2 border-rose-500 bg-rose-500/25 rounded shadow-[0_0_18px_rgba(244,63,94,0.7)] flex items-start justify-end p-0.5 animate-pulse z-10"
              >
                <span className="text-[10px] font-mono font-bold bg-rose-600 text-white px-1.5 py-0.5 rounded shadow">
                  {proposal.selected_entity_id ? `${proposal.selected_entity_type}:${proposal.selected_entity_id}` : 'HAZARD'}
                </span>
              </div>
            )}
          </div>
        )}

        {/* HUD Crosshairs Overlay */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-2 left-2 text-[10px] font-mono text-cyan-400 bg-black/60 px-1.5 py-0.5 rounded border border-cyan-800/60">
            REC • 1080p • 60 FPS • ARGON PERCEPTION
          </div>
          {/* Viewfinder corner brackets */}
          <div className="absolute top-3 left-3 w-5 h-5 border-t-2 border-l-2 border-cyan-400/60" />
          <div className="absolute top-3 right-3 w-5 h-5 border-t-2 border-r-2 border-cyan-400/60" />
          <div className="absolute bottom-3 left-3 w-5 h-5 border-b-2 border-l-2 border-cyan-400/60" />
          <div className="absolute bottom-3 right-3 w-5 h-5 border-b-2 border-r-2 border-cyan-400/60" />
        </div>
      </div>

      {/* Bottom Control Bar */}
      <div className="px-3 py-2 bg-slate-900 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
        {/* Thinking Level Selector */}
        <div className="flex items-center space-x-2">
          <span className="text-[11px] text-slate-400 font-semibold font-mono">Thinking Level:</span>
          <div className="inline-flex rounded bg-slate-950 border border-slate-800 p-0.5">
            {(['low', 'medium', 'high'] as const).map((lvl) => (
              <button
                key={lvl}
                onClick={() => setThinkingLevel(lvl)}
                className={`px-2 py-0.5 text-[10px] rounded font-bold uppercase transition ${
                  thinkingLevel === lvl
                    ? 'bg-cyan-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>

        {/* Snap & Detect Button */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => handleTriggerDetection('P2')}
            disabled={isGroundingLoading}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-md text-xs font-bold shadow-neon-cyan transition"
          >
            <Camera className="h-3.5 w-3.5" />
            <span>{isGroundingLoading ? 'Argon Detecting...' : 'Snap & Ground via Argon'}</span>
          </button>
          <button
            onClick={onApplyProposal}
            className="flex items-center space-x-1 px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-md text-xs font-bold shadow-neon-rose transition"
            title="Commit detected blockage to state"
          >
            <span>Apply Blockage</span>
          </button>
        </div>
      </div>
    </div>
  );
};