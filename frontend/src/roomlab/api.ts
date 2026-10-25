import type {
  RoomSceneV1,
  MediaRecord,
  JobRecord,
  EditSceneRequest,
  CalibrateRequest,
  SolveRequest,
  SolveResult,
  OptimizeResult,
  ValidationReport,
} from "./contracts.generated";
export type Config = {
  gemini_configured: boolean;
  model: string;
  max_video_seconds: number;
  max_upload_bytes: number;
  sample_video_url: string | null;
};
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/roomlab" + path, init);
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail ?? body),
    );
  return body as T;
}
const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const getConfig = () => request<Config>("/config");
export const uploadVideo = (file: File) => {
  const body = new FormData();
  body.append("file", file);
  return request<MediaRecord>("/media", { method: "POST", body });
};
export const getMedia = (id: string) =>
  request<MediaRecord>("/media/" + encodeURIComponent(id));
export const extractRoom = (media_id: string) =>
  request<JobRecord>("/extractions", json({ media_id }));
export const getJob = (id: string) =>
  request<JobRecord>("/jobs/" + encodeURIComponent(id));
export const cancelJob = (id: string) =>
  request<JobRecord>("/jobs/" + encodeURIComponent(id), { method: "DELETE" });
export const getScene = (id: string) =>
  request<RoomSceneV1>("/scenes/" + encodeURIComponent(id));
export const saveScene = (id: string, body: EditSceneRequest) =>
  request<RoomSceneV1>(
    "/scenes/" + encodeURIComponent(id),
    json(body, "PATCH"),
  );
export const importScene = (scene: RoomSceneV1) =>
  request<RoomSceneV1>("/scenes", json(scene));
export const calibrateScene = (id: string, body: CalibrateRequest) =>
  request<RoomSceneV1>(
    "/scenes/" + encodeURIComponent(id) + "/calibrate",
    json(body),
  );
export const validateScene = (id: string) =>
  request<ValidationReport>(
    "/scenes/" + encodeURIComponent(id) + "/validate",
    json({}),
  );
export const solveScene = (id: string, body: SolveRequest) =>
  request<SolveResult>(
    "/scenes/" + encodeURIComponent(id) + "/solve",
    json(body),
  );
export const optimizeScene = (id: string, body: SolveRequest) =>
  request<OptimizeResult>(
    "/scenes/" + encodeURIComponent(id) + "/optimize",
    json(body),
  );

export const getSceneReceipt = (id: string) =>
  request<import("./contracts.generated").SceneReceipt>(
    "/scenes/" + encodeURIComponent(id) + "/receipt",
  );
export const requestCritique = (
  id: string,
  body: import("./contracts.generated").CritiqueRequest,
) =>
  request<import("./contracts.generated").CritiqueJobRecord>(
    "/scenes/" + encodeURIComponent(id) + "/critique",
    json(body),
  );
export const getCritiqueJob = (id: string) =>
  request<import("./contracts.generated").CritiqueJobRecord>(
    "/critique-jobs/" + encodeURIComponent(id),
  );
export const cancelCritiqueJob = (id: string) =>
  request<import("./contracts.generated").CritiqueJobRecord>(
    "/critique-jobs/" + encodeURIComponent(id),
    { method: "DELETE" },
  );
export const proposeOverlapRepair = (
  id: string,
  body: import("./contracts.generated").RepairRequest,
) =>
  request<import("./contracts.generated").RepairResult>(
    "/scenes/" + encodeURIComponent(id) + "/repair-overlaps",
    json(body),
  );

export const getRoomLibrary = () => request<import('./contracts.generated').RoomLibrary>('/rooms');
