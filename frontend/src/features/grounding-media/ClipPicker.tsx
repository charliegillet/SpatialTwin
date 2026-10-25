import { useEffect, useId, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { Film, Image as ImageIcon } from 'lucide-react';
import { readVideoDuration, validateClip } from './clip';
import './ClipPicker.css';

export type GroundingMediaKind = 'image' | 'video';
export interface GroundingSelection { kind: GroundingMediaKind; file: File }

interface ClipPickerProps {
  videoEnabled: boolean;
  onSelect: (selection: GroundingSelection) => void;
  disabled?: boolean;
}

export function ClipPicker({ videoEnabled, onSelect, disabled = false }: ClipPickerProps) {
  const uid = useId();
  const [kind, setKind] = useState<GroundingMediaKind>('image');
  const [message, setMessage] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const input = useRef<HTMLInputElement | null>(null);
  const token = useRef(0);
  const effectiveKind: GroundingMediaKind = videoEnabled ? kind : 'image';

  useEffect(() => () => { token.current += 1; }, []);

  function chooseKind(next: GroundingMediaKind) {
    if (next === 'video' && !videoEnabled) return;
    token.current += 1;
    setKind(next);
    setMessage(null);
    setChecking(false);
    if (input.current) input.current.value = '';
  }

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const mine = ++token.current;
    setMessage(null);
    if (effectiveKind === 'image') {
      if (!file.type.startsWith('image/')) {
        setMessage({ tone: 'error', text: 'Choose an image file.' });
        return;
      }
      setMessage({ tone: 'ok', text: `Selected ${file.name}.` });
      onSelect({ kind: 'image', file });
      return;
    }
    setChecking(true);
    const durationSeconds = await readVideoDuration(file);
    if (mine !== token.current) return;
    setChecking(false);
    const result = validateClip({ type: file.type, size: file.size, durationSeconds });
    if (!result.ok) {
      setMessage({ tone: 'error', text: result.reason });
      return;
    }
    setMessage({ tone: 'ok', text: `Selected ${file.name}.` });
    onSelect({ kind: 'video', file });
  }

  const noteId = `${uid}-note`;
  const msgId = `${uid}-msg`;
  return (
    <section className="clip-picker" aria-labelledby={`${uid}-title`}>
      <h3 id={`${uid}-title`}>Grounding media</h3>
      <div className="clip-picker-modes" role="group" aria-label="Media type">
        <button type="button" className={effectiveKind === 'image' ? 'is-active' : ''} aria-pressed={effectiveKind === 'image'}
          disabled={disabled} onClick={() => chooseKind('image')}><ImageIcon size={15} aria-hidden="true" />Image</button>
        <button type="button" className={effectiveKind === 'video' ? 'is-active' : ''} aria-pressed={effectiveKind === 'video'}
          disabled={disabled || !videoEnabled} aria-describedby={videoEnabled ? undefined : noteId}
          onClick={() => chooseKind('video')}><Film size={15} aria-hidden="true" />Video</button>
      </div>
      {!videoEnabled && (
        <p id={noteId} className="clip-picker-note">Video unavailable. Still images only.</p>
      )}
      {videoEnabled && effectiveKind === 'video' && (
        <p className="clip-picker-note">MP4 or WebM, up to 8 MB and 15 seconds.</p>
      )}
      <label className="clip-picker-file">
        <span>{effectiveKind === 'video' ? 'Choose clip' : 'Choose image'}</span>
        <input ref={input} type="file" accept={effectiveKind === 'video' ? 'video/mp4,video/webm' : 'image/*'}
          disabled={disabled || checking} onChange={onFile} aria-describedby={message ? msgId : undefined} />
      </label>
      <p id={msgId} className={`clip-picker-message${message?.tone === 'error' ? ' is-error' : ''}`}
        role={message?.tone === 'error' ? 'alert' : 'status'}>
        {checking ? 'Reading clip duration' : message?.text ?? ''}
      </p>
    </section>
  );
}
