import { PLAYBACK_CAPTION, type PlaybackView } from '../twin/playback.ts';
import type { Playback } from './usePlayback.ts';

export default function PlaybackBar({ view, playback }: { view: PlaybackView; playback: Playback }) {
  return (
    <div className="twin-playback" role="group" aria-label="Evacuation playback">
      <div className="twin-playback__row">
        <button type="button" onClick={playback.toggle} aria-label={playback.playing ? 'Pause playback' : 'Play playback'}>
          {playback.playing ? 'Pause' : view.atEnd ? 'Replay' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={view.last}
          step={1}
          value={view.index}
          onChange={(event) => playback.scrub(Number(event.target.value))}
          aria-label="Playback time"
          aria-valuetext={view.timeLabel}
        />
        <span className="twin-playback__time">{view.timeLabel}</span>
      </div>
      <div className="twin-playback__note">
        {PLAYBACK_CAPTION}
        {view.transit ? ` · ${view.transit}` : ''}
      </div>
    </div>
  );
}
