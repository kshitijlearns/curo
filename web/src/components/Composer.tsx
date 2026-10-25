'use client';
/** The Composer: type or speak (Web Speech API), then send. Enter sends; Shift+Enter breaks. */
import { useRef, useState } from 'react';

import { Icon } from './Icon';
import { useVoice } from '@/lib/voice';

export function Composer({
  placeholder,
  hint,
  busy,
  onSend,
  onNotice,
  onTyping,
}: {
  placeholder: string;
  hint?: string;
  busy?: boolean;
  onSend: (text: string) => void;
  onNotice: (text: string) => void;
  /** v2.2: the persona row listens while there's text in the box. */
  onTyping?: (typing: boolean) => void;
}) {
  const [text, setText] = useState('');
  const base = useRef('');
  const voice = useVoice((heard, final) => {
    setText(`${base.current}${base.current ? ' ' : ''}${heard}`.trimStart());
    if (final) base.current = '';
  });

  const send = () => {
    const t = text.trim();
    if (!t || busy) return;
    voice.stop();
    onSend(t);
    setText('');
    onTyping?.(false);
  };

  const mic = () => {
    if (voice.listening) return voice.stop();
    base.current = text;
    const problem = voice.start();
    if (problem) onNotice(problem);
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <label className="sr-only" htmlFor="composer">
          {placeholder}
        </label>
        <textarea
          id="composer"
          rows={1}
          value={text}
          placeholder={voice.listening ? 'Listening…' : placeholder}
          onChange={(e) => {
            setText(e.target.value);
            onTyping?.(e.target.value.trim().length > 0);
          }}
          onBlur={() => onTyping?.(false)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={busy}
        />
        {text.trim() ? (
          <button className="send" onClick={send} disabled={busy} aria-label="Send">
            {busy ? <span className="spinner" style={{ borderTopColor: '#fff' }} /> : <Icon name="send" size={20} strokeWidth={2} />}
          </button>
        ) : (
          <button
            className="mic"
            onClick={mic}
            aria-pressed={voice.listening}
            aria-label={voice.listening ? 'Stop listening' : 'Speak instead of typing'}
            disabled={busy}
          >
            <Icon name="mic" size={20} />
          </button>
        )}
      </div>
      {hint ? <p className="hint small muted" style={{ margin: '6px 8px 0' }}>{hint}</p> : null}
    </div>
  );
}
