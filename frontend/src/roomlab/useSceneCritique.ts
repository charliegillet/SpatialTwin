import { useEffect, useRef, useState } from "react";
import type {
  RoomSceneV1,
  CritiqueJobRecord,
  CritiqueResult,
  SolveRequest,
} from "./contracts.generated";
import {
  getSceneReceipt,
  requestCritique,
  getCritiqueJob,
  cancelCritiqueJob,
} from "./api";

export function useSceneCritique(
  scene: RoomSceneV1 | null,
  dirty: boolean,
  contextVersion: number,
) {
  const [job, setJob] = useState<CritiqueJobRecord | null>(null),
    [result, setResult] = useState<CritiqueResult | null>(null);
  const [error, setError] = useState<string | null>(null),
    [busy, setBusy] = useState(false);
  const seq = useRef(0),
    jobRef = useRef<string | null>(null),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancel = () => {
    seq.current++;
    if (timer.current) clearTimeout(timer.current);
    if (jobRef.current) void cancelCritiqueJob(jobRef.current).catch(() => {});
    jobRef.current = null;
    setBusy(false);
  };
  useEffect(() => {
    cancel();
    setJob(null);
    setResult(null);
    setError(null);
    return () => {
      seq.current++;
      if (timer.current) clearTimeout(timer.current);
      if (jobRef.current)
        void cancelCritiqueJob(jobRef.current).catch(() => {});
      jobRef.current = null;
    };
  }, [scene, dirty, contextVersion]);
  const start = async (solveRequest: SolveRequest, focus: string[]) => {
    if (!scene || dirty || busy) return;
    cancel();
    const token = seq.current;
    setBusy(true);
    setResult(null);
    setError(null);
    try {
      const receipt = await getSceneReceipt(scene.scene_id);
      if (token !== seq.current) return;
      if (receipt.scene_revision !== scene.scene_revision)
        throw new Error("The saved room changed. Reload before reviewing.");
      const created = await requestCritique(scene.scene_id, {
        expected_revision: scene.scene_revision,
        geometry_hash: receipt.geometry_hash,
        evidence_hash: receipt.evidence_hash,
        focus_element_ids: focus,
        solve_request: solveRequest,
      });
      if (token !== seq.current) {
        void cancelCritiqueJob(created.job_id).catch(() => {});
        return;
      }
      jobRef.current = created.job_id;
      setJob(created);
      const poll = async () => {
        try {
          const updated = await getCritiqueJob(created.job_id);
          if (token !== seq.current) return;
          setJob(updated);
          if (updated.status === "completed") {
            const r = updated.result;
            if (
              !r ||
              r.scene_id !== scene.scene_id ||
              r.scene_revision !== scene.scene_revision ||
              r.geometry_hash !== receipt.geometry_hash ||
              r.evidence_hash !== receipt.evidence_hash
            )
              throw new Error("Review receipt does not match this room.");
            setResult(r);
            setBusy(false);
            jobRef.current = null;
          } else if (
            updated.status === "failed" ||
            updated.status === "cancelled"
          ) {
            setError(updated.error ?? "Review cancelled.");
            setBusy(false);
            jobRef.current = null;
          } else timer.current = setTimeout(poll, 1000);
        } catch (e) {
          if (token !== seq.current) return;
          setError(e instanceof Error ? e.message : String(e));
          setBusy(false);
          if (jobRef.current)
            void cancelCritiqueJob(jobRef.current).catch(() => {});
          jobRef.current = null;
        }
      };
      await poll();
    } catch (e) {
      if (token !== seq.current) return;
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };
  return { job, result, error, busy, start, cancel };
}
