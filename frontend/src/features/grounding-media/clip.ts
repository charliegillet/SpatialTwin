export const MAX_CLIP_BYTES = 8 * 1024 * 1024;
export const MAX_CLIP_SECONDS = 15;
export const ALLOWED_VIDEO_MIME = ['video/mp4', 'video/webm'] as const;

export interface ClipCandidate {
  type: string;
  size: number;
  durationSeconds?: number;
}

export type ClipValidation = { ok: true } | { ok: false; reason: string };

export function validateClip(file: ClipCandidate): ClipValidation {
  if (!(ALLOWED_VIDEO_MIME as readonly string[]).includes(file.type)) {
    return { ok: false, reason: 'Video must be MP4 or WebM.' };
  }
  if (!Number.isFinite(file.size) || file.size <= 0) {
    return { ok: false, reason: 'The video file is empty.' };
  }
  if (file.size > MAX_CLIP_BYTES) {
    return { ok: false, reason: `Video must be 8 MB or smaller.` };
  }
  const seconds = file.durationSeconds;
  if (seconds === undefined || !Number.isFinite(seconds)) {
    return { ok: false, reason: `Duration could not be read in this browser, so the ${MAX_CLIP_SECONDS} second limit needs a server-side check. The clip was not accepted.` };
  }
  if (seconds > MAX_CLIP_SECONDS) {
    return { ok: false, reason: `Video must be ${MAX_CLIP_SECONDS} seconds or shorter.` };
  }
  return { ok: true };
}

/** Reads duration from a hidden video element; resolves undefined when it cannot be read. */
export function readVideoDuration(file: Blob, timeoutMs = 5000): Promise<number | undefined> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    let settled = false;
    const finish = (value: number | undefined) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      video.removeAttribute('src');
      video.load();
      URL.revokeObjectURL(url);
      resolve(value);
    };
    const timer = window.setTimeout(() => finish(undefined), timeoutMs);
    video.preload = 'metadata';
    video.muted = true;
    video.onloadedmetadata = () => finish(Number.isFinite(video.duration) && video.duration > 0 ? video.duration : undefined);
    video.onerror = () => finish(undefined);
    video.src = url;
  });
}
