/**
 * On-device speech recognition for the Composer's mic.
 *
 * Uses expo-speech-recognition, whose native code is NOT in Expo Go: importing it there
 * throws. So we check for the native module first and load the library only when it
 * exists (development or store builds) or on web. In Expo Go, `useVoiceInput().available`
 * is false and the Composer explains that the keyboard's own mic still works.
 */
import { requireOptionalNativeModule } from 'expo';
import { useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';

type SpeechLib = typeof import('expo-speech-recognition');
type Subscription = { remove(): void };

let cached: SpeechLib | null | undefined;

export function speechLib(): SpeechLib | null {
  if (cached !== undefined) return cached;
  const hasNative =
    Platform.OS === 'web' || requireOptionalNativeModule('ExpoSpeechRecognition') != null;
  // A static import would throw in Expo Go, so the library is loaded only when present.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  cached = hasNative ? (require('expo-speech-recognition') as SpeechLib) : null;
  return cached;
}

/** Indian English recognises Hinglish reasonably; a creator language setting can change it. */
export const DEFAULT_SPEECH_LANG = 'en-IN';

export type VoiceProblem = 'unavailable' | 'permission' | 'failed';

export function useVoiceInput(
  onFinal: (text: string) => void,
  onProblem: (problem: VoiceProblem) => void,
  lang: string = DEFAULT_SPEECH_LANG,
) {
  const [listening, setListening] = useState(false);
  const [partial, setPartial] = useState('');
  const subs = useRef<Subscription[]>([]);
  // Latest callbacks for the native event listeners, updated after each render.
  const latest = useRef({ onFinal, onProblem });
  useEffect(() => {
    latest.current = { onFinal, onProblem };
  });

  const clear = () => {
    subs.current.forEach((s) => s.remove());
    subs.current = [];
  };

  useEffect(
    () => () => {
      clear();
      speechLib()?.ExpoSpeechRecognitionModule.abort();
    },
    [],
  );

  async function start() {
    const lib = speechLib();
    if (!lib) {
      latest.current.onProblem('unavailable');
      return;
    }
    const M = lib.ExpoSpeechRecognitionModule;
    const permission = await M.requestPermissionsAsync();
    if (!permission.granted) {
      latest.current.onProblem('permission');
      return;
    }
    clear();
    let finalText = '';
    let lastText = '';
    subs.current.push(
      M.addListener('result', (e) => {
        const text = e.results[0]?.transcript ?? '';
        lastText = text;
        if (e.isFinal) finalText = text;
        setPartial(text);
      }),
      M.addListener('error', (e) => {
        if (e.error !== 'aborted' && e.error !== 'no-speech' && e.error !== 'speech-timeout') {
          latest.current.onProblem(e.error === 'not-allowed' ? 'permission' : 'failed');
        }
      }),
      M.addListener('end', () => {
        clear();
        setListening(false);
        setPartial('');
        const text = (finalText || lastText).trim();
        if (text) latest.current.onFinal(text);
      }),
    );
    M.start({ lang, interimResults: true, continuous: false, addsPunctuation: true });
    setListening(true);
  }

  function stop() {
    speechLib()?.ExpoSpeechRecognitionModule.stop();
  }

  return { listening, partial, start, stop };
}
