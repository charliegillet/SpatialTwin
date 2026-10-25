import React, { useState } from 'react';
import { Navigation, Wand2, CheckCircle, AlertTriangle, HelpCircle, Activity } from 'lucide-react';
import type { OptimizeResult, RoomSceneV1, SolveRequest, SolveResult } from './contracts.generated';
import { conditionalGapPassProbability } from './editorState';

interface ClearancePanelProps {
  scene: RoomSceneV1 | null;
  dirty: boolean;
  startPoint: [number, number];
  goalPoint: [number, number];
  agentDiameterM: number;
  marginM: number;
  solveResult: SolveResult | null;
  optimizeResult: OptimizeResult | null;
  isSolving: boolean;
  isOptimizing: boolean;
  pickEndpointMode: 'start' | 'goal' | null;
  onChangeStart: (pt: [number, number]) => void;
  onChangeGoal: (pt: [number, number]) => void;
  onChangeAgentDiameter: (d: number) => void;
  onChangeMargin: (m: number) => void;
  onTogglePickEndpoint: (mode: 'start' | 'goal' | null) => void;
  onRunSolve: (req: SolveRequest) => void;
  onRunOptimize: (req: SolveRequest) => void;
  onApplyOptimizedScene: (nextScene: RoomSceneV1) => void;
}

export const ClearancePanel: React.FC<ClearancePanelProps> = ({
  scene,
  dirty,
  startPoint,
  goalPoint,
  agentDiameterM,
  marginM,
  solveResult,
  optimizeResult,
  isSolving,
  isOptimizing,
  pickEndpointMode,
  onChangeStart,
  onChangeGoal,
  onChangeAgentDiameter,
  onChangeMargin,
  onTogglePickEndpoint,
  onRunSolve,
  onRunOptimize,
  onApplyOptimizedScene,
}) => {
  const [showGaussianEdu, setShowGaussianEdu] = useState<boolean>(false);
  const [assumedMeanGapM, setAssumedMeanGapM] = useState<number>(0.78);
  const [assumedSigmaM, setAssumedSigmaM] = useState<number>(0.08);

  if (!scene) return null;

  const requiredWidth = agentDiameterM + 2 * marginM;
  const triggerSolve = () => {
    onRunSolve({
      expected_revision: scene.scene_revision ?? 1,
      start: [startPoint[0], startPoint[1]],
      goal: [goalPoint[0], goalPoint[1]],
      agent_diameter_m: agentDiameterM,
      margin_m: marginM,
    });
  };

  const triggerOptimize = () => {
    onRunOptimize({
      expected_revision: scene.scene_revision ?? 1,
      start: [startPoint[0], startPoint[1]],
      goal: [goalPoint[0], goalPoint[1]],
      agent_diameter_m: agentDiameterM,
      margin_m: marginM,
    });
  };

  const effectiveMean =
    solveResult?.minimum_clearance_m != null && solveResult.minimum_clearance_m > 0
      ? solveResult.minimum_clearance_m + requiredWidth
      : assumedMeanGapM;
  const condProb = conditionalGapPassProbability(requiredWidth, effectiveMean, assumedSigmaM);

  return (
    <section className="rl-panel" aria-label="Clearance and Reachability">
      <div className="rl-panel-header">
        <span className="rl-panel-title">
          <Navigation size={15} /> Planar Disc Reachability & Layout Search
        </span>
        <span className="rl-badge">Required Width: {requiredWidth.toFixed(2)}m</span>
      </div>

      <p className="rl-muted-note">
        2D planar circular-agent clearance check (educational approximation, not a kinematic wheelchair certification).
      </p>

      <div className="rl-preset-row">
        <button
          type="button"
          className={`rl-pill ${Math.abs(agentDiameterM - 0.55) < 0.02 ? 'rl-pill--active' : ''}`}
          onClick={() => onChangeAgentDiameter(0.55)}
        >
          <span>Walking Person (0.55m)</span>
        </button>
        <button
          type="button"
          className={`rl-pill ${Math.abs(agentDiameterM - 0.75) < 0.02 ? 'rl-pill--active' : ''}`}
          onClick={() => onChangeAgentDiameter(0.75)}
        >
          <span>Rolling Cart (0.75m)</span>
        </button>
        <button
          type="button"
          className={`rl-pill ${Math.abs(agentDiameterM - 0.9) < 0.02 ? 'rl-pill--active' : ''}`}
          onClick={() => onChangeAgentDiameter(0.9)}
        >
          <span>Wide Carrier (0.90m)</span>
        </button>
      </div>

      <div className="rl-field-row">
        <label className="rl-field">
          <span>Agent Diameter: {agentDiameterM.toFixed(2)}m</span>
          <input
            type="range"
            min="0.30"
            max="1.40"
            step="0.02"
            value={agentDiameterM}
            onChange={(e) => onChangeAgentDiameter(parseFloat(e.target.value))}
          />
        </label>
        <label className="rl-field">
          <span>Margin/Side: {marginM.toFixed(2)}m</span>
          <input
            type="range"
            min="0.00"
            max="0.25"
            step="0.01"
            value={marginM}
            onChange={(e) => onChangeMargin(parseFloat(e.target.value))}
          />
        </label>
      </div>

      <div className="rl-field-row">
        <div className="rl-field">
          <span>
            Start [X, Z]: [{startPoint[0].toFixed(2)}, {startPoint[1].toFixed(2)}]
          </span>
          <div className="rl-inline-inputs">
            <input
              type="number"
              step="0.1"
              value={startPoint[0]}
              onChange={(e) => onChangeStart([parseFloat(e.target.value) || 0, startPoint[1]])}
            />
            <input
              type="number"
              step="0.1"
              value={startPoint[1]}
              onChange={(e) => onChangeStart([startPoint[0], parseFloat(e.target.value) || 0])}
            />
            <button
              type="button"
              className={`rl-btn rl-btn--xs ${pickEndpointMode === 'start' ? 'rl-btn--active' : ''}`}
              onClick={() => onTogglePickEndpoint(pickEndpointMode === 'start' ? null : 'start')}
            >
              Pick on Floor
            </button>
          </div>
        </div>
      </div>

      <div className="rl-field-row">
        <div className="rl-field">
          <span>
            Goal [X, Z]: [{goalPoint[0].toFixed(2)}, {goalPoint[1].toFixed(2)}]
          </span>
          <div className="rl-inline-inputs">
            <input
              type="number"
              step="0.1"
              value={goalPoint[0]}
              onChange={(e) => onChangeGoal([parseFloat(e.target.value) || 0, goalPoint[1]])}
            />
            <input
              type="number"
              step="0.1"
              value={goalPoint[1]}
              onChange={(e) => onChangeGoal([goalPoint[0], parseFloat(e.target.value) || 0])}
            />
            <button
              type="button"
              className={`rl-btn rl-btn--xs ${pickEndpointMode === 'goal' ? 'rl-btn--active' : ''}`}
              onClick={() => onTogglePickEndpoint(pickEndpointMode === 'goal' ? null : 'goal')}
            >
              Pick on Floor
            </button>
          </div>
        </div>
      </div>

      <div className="rl-action-pair">
        <button
          type="button"
          className="rl-btn rl-btn--primary"
          disabled={isSolving || dirty}
          onClick={triggerSolve}
          title={dirty ? 'Save local edits before running authoritative clearance solver' : undefined}
        >
          <Navigation size={14} />
          <span>{dirty ? 'Save First to Test' : isSolving ? 'Solving…' : 'Test Reachability'}</span>
        </button>

        <button
          type="button"
          className="rl-btn rl-btn--accent"
          disabled={isOptimizing || dirty}
          onClick={triggerOptimize}
          title="Search bounded translations of movable furniture for a verified passable candidate"
        >
          <Wand2 size={14} />
          <span>{isOptimizing ? 'Searching…' : 'Search Furniture Moves'}</span>
        </button>
      </div>

      {solveResult && (
        <div className={`rl-solve-card rl-solve-card--${solveResult.status}`}>
          <div className="rl-solve-header">
            {solveResult.status === 'ROBUST_PASS' && <CheckCircle size={15} />}
            {solveResult.status === 'ROBUST_BLOCKED' && <AlertTriangle size={15} />}
            {solveResult.status !== 'ROBUST_PASS' && solveResult.status !== 'ROBUST_BLOCKED' && (
              <HelpCircle size={15} />
            )}
            <strong>{solveResult.status}</strong>
            {solveResult.path_length_m != null && <span>Path: {solveResult.path_length_m.toFixed(2)}m</span>}
            {solveResult.minimum_clearance_m != null && (
              <span>Slack: {solveResult.minimum_clearance_m.toFixed(2)}m</span>
            )}
          </div>
          <p className="rl-solve-msg">{solveResult.message}</p>

          {solveResult.evidence_requests && solveResult.evidence_requests.length > 0 && (
            <div className="rl-evidence-req">
              <strong>Targeted Evidence / Measurement Needed:</strong>
              <ul>
                {solveResult.evidence_requests.map((req, idx) => (
                  <li key={idx}>{req}</li>
                ))}
              </ul>
            </div>
          )}

          {solveResult.assumptions && solveResult.assumptions.length > 0 && (
            <details className="rl-assumptions-details">
              <summary>Solver Assumptions ({solveResult.assumptions.length})</summary>
              <ul>
                {solveResult.assumptions.map((a, idx) => (
                  <li key={idx}>{a}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {optimizeResult && (
        <div className={`rl-opt-card rl-opt-card--${optimizeResult.status}`}>
          <div className="rl-solve-header">
            <strong>Layout Search ({optimizeResult.status})</strong>
            <span>{optimizeResult.candidates_checked ?? 0} candidates checked</span>
          </div>
          <p className="rl-solve-msg">{optimizeResult.message}</p>
          {optimizeResult.object_id && optimizeResult.translation && (
            <p className="rl-muted-note">
              Best verified candidate within search budget: move <code>{optimizeResult.object_id}</code> by ΔX=
              {optimizeResult.translation[0].toFixed(2)}m, ΔZ={optimizeResult.translation[1].toFixed(2)}m (final-layout
              suggestion).
            </p>
          )}
          {optimizeResult.scene && (
            <button
              type="button"
              className="rl-btn rl-btn--primary rl-btn--full"
              onClick={() => onApplyOptimizedScene(optimizeResult.scene!)}
            >
              <span>Preview & Stage Candidate Layout</span>
            </button>
          )}
        </div>
      )}

      <div className="rl-edu-toggle">
        <button
          type="button"
          className="rl-btn rl-btn--xs rl-btn--full"
          onClick={() => setShowGaussianEdu((v) => !v)}
        >
          <Activity size={13} />
          <span>
            {showGaussianEdu
              ? 'Hide Educational Conditional Gaussian Gap Curve'
              : 'Show Educational Conditional Gaussian Gap Model'}
          </span>
        </button>

        {showGaussianEdu && (
          <div className="rl-edu-card">
            <p className="rl-muted-note">
              <strong>Educational Conditional Model:</strong> If a single bottleneck gap is modeled as{' '}
              <code>W ~ Normal(μ, σ²)</code>, the tail integral is{' '}
              <code>P(W ≥ d+2m) = ½ erfc((d+2m - μ)/(σ√2))</code>. (Assumed distribution, not an empirical safety
              probability.)
            </p>
            <div className="rl-field-row">
              <label className="rl-field">
                <span>Assumed Mean μ: {effectiveMean.toFixed(2)}m</span>
                <input
                  type="range"
                  min="0.30"
                  max="1.60"
                  step="0.02"
                  value={assumedMeanGapM}
                  onChange={(e) => setAssumedMeanGapM(parseFloat(e.target.value))}
                />
              </label>
              <label className="rl-field">
                <span>Assumed Std σ: {assumedSigmaM.toFixed(2)}m</span>
                <input
                  type="range"
                  min="0.00"
                  max="0.35"
                  step="0.01"
                  value={assumedSigmaM}
                  onChange={(e) => setAssumedSigmaM(parseFloat(e.target.value))}
                />
              </label>
            </div>
            <div className="rl-edu-metric">
              <span>Conditional Tail Integral P(W ≥ {requiredWidth.toFixed(2)}m):</span>
              <strong>{(condProb * 100).toFixed(1)}%</strong>
            </div>
            <svg viewBox="0 0 260 70" className="rl-gauss-svg" aria-label="Conditional Gaussian density curve">
              {(() => {
                const xMin = 0.2;
                const xMax = 1.6;
                const sigma = Math.max(0.015, assumedSigmaM);
                const pts: string[] = [];
                const fillPts: string[] = [];
                const mapX = (w: number) => 10 + ((w - xMin) / (xMax - xMin)) * 240;
                const peak = 1 / (sigma * Math.sqrt(2 * Math.PI));
                for (let i = 0; i <= 80; i++) {
                  const w = xMin + ((xMax - xMin) * i) / 80;
                  const density =
                    (1 / (sigma * Math.sqrt(2 * Math.PI))) *
                    Math.exp(-0.5 * Math.pow((w - effectiveMean) / sigma, 2));
                  const sx = mapX(w);
                  const sy = 58 - (density / peak) * 46;
                  pts.push(`${sx.toFixed(1)},${sy.toFixed(1)}`);
                  if (w >= requiredWidth) {
                    fillPts.push(`${sx.toFixed(1)},${sy.toFixed(1)}`);
                  }
                }
                const threshX = mapX(Math.min(xMax, Math.max(xMin, requiredWidth)));
                return (
                  <>
                    <line x1="10" y1="58" x2="250" y2="58" stroke="#334155" strokeWidth="1" />
                    {fillPts.length > 1 && (
                      <polygon
                        points={`${threshX.toFixed(1)},58 ${fillPts.join(' ')} 250,58`}
                        fill="rgba(56, 189, 248, 0.28)"
                      />
                    )}
                    <polyline fill="none" stroke="#38bdf8" strokeWidth="2" points={pts.join(' ')} />
                    <line
                      x1={threshX}
                      y1="8"
                      x2={threshX}
                      y2="60"
                      stroke="#f43f5e"
                      strokeWidth="1.5"
                      strokeDasharray="3,2"
                    />
                  </>
                );
              })()}
            </svg>
          </div>
        )}
      </div>
    </section>
  );
};
