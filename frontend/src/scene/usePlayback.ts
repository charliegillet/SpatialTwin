import { useCallback, useEffect, useRef, useState } from 'react';
import { clampIndex, frames, lastIndex, stepDelayMs } from '../twin/playback.ts';
import type { DoorPlanResponse } from '../twin/types.ts';

export interface Playback {
  index: number;
  playing: boolean;
  toggle: () => void;
  scrub: (index: number) => void;
}

/** A new plan (or none) resets playback: autoplay 0 -> end once, then hold. Reduced motion shows the final frame. */
export function usePlayback(plan: DoorPlanResponse | null, reducedMotion: boolean): Playback {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasFrames = frames(plan).length > 0;

  const stop = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  useEffect(() => {
    stop();
    if (!plan || !hasFrames) {
      setIndex(0);
      setPlaying(false);
    } else if (reducedMotion) {
      setIndex(lastIndex(plan));
      setPlaying(false);
    } else {
      setIndex(0);
      setPlaying(true);
    }
    return stop;
  }, [plan, hasFrames, reducedMotion]);

  useEffect(() => {
    if (!playing || !plan) return;
    if (index >= lastIndex(plan)) {
      setPlaying(false);
      return;
    }
    timer.current = setTimeout(() => setIndex((i) => clampIndex(plan, i + 1)), stepDelayMs(plan));
    return stop;
  }, [playing, index, plan]);

  const toggle = useCallback(() => {
    if (!plan || !hasFrames) return;
    if (playing) { setPlaying(false); return; }
    if (index >= lastIndex(plan)) setIndex(0);
    setPlaying(true);
  }, [plan, hasFrames, playing, index]);
  const scrub = useCallback((next: number) => {
    setPlaying(false);
    setIndex(clampIndex(plan, next));
  }, [plan]);

  return { index: plan ? clampIndex(plan, index) : 0, playing, toggle, scrub };
}
