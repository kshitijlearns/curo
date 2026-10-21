'use client';
/**
 * Voice input for the Composer through the browser's Web Speech API (no audio leaves the
 * browser for CURO's servers). English (India) by default, so Hinglish is heard well; where the
 * browser has no speech recognition the mic button explains that instead of failing silently.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: any) => void) | null;
  onerror: ((e: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function make(): Recognition | null {
  if (typeof window === 'undefined') return null;
  const W = window as any;
  const Ctor = W.SpeechRecognition || W.webkitSpeechRecognition;
  return Ctor ? (new Ctor() as Recognition) : null;
}

export function useVoice(onText: (text: string, final: boolean) => void) {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(true);
  const rec = useRef<Recognition | null>(null);
  const cb = useRef(onText);
  cb.current = onText;

  useEffect(() => {
    setSupported(Boolean(make()));
    return () => rec.current?.stop();
  }, []);

  const start = useCallback((): string | null => {
    const r = make();
    if (!r) return 'Voice input isn’t available in this browser. Try Chrome, Edge or Safari.';
    r.lang = 'en-IN';
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e: any) => {
      let text = '';
      let final = false;
      for (let i = 0; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
        if (e.results[i].isFinal) final = true;
      }
      cb.current(text, final);
    };
    r.onerror = () => setListening(false);
    r.onend = () => setListening(false);
    rec.current = r;
    try {
      r.start();
      setListening(true);
      return null;
    } catch {
      return 'Couldn’t start the microphone. Check the browser’s permission.';
    }
  }, []);

  const stop = useCallback(() => {
    rec.current?.stop();
    setListening(false);
  }, []);

  return { listening, supported, start, stop };
}
