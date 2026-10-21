import { cachedSimulation } from '@/api/simulator';
import type { AppState } from '@/state/app';

export type ComposerConfig = { key: string; placeholder: string; hint?: string };

/**
 * Which composer shows, and its placeholder and hint line, for the current screen
 * (prototype `composer` mapping). No composer on Home, Saved, the final draft or the
 * Simulator before a result.
 */
export function composerFor(
  s: Pick<AppState, 'tab' | 'overlay' | 'studio' | 'sim'>,
): ComposerConfig | null {
  if (s.overlay) return null;
  if (s.tab === 'studio') {
    const st = s.studio;
    const validating = !st.projectId && !st.oppName && !st.busy;
    if (validating) return { key: 'validate', placeholder: 'Type your idea or thoughts…' };
    switch (st.stage) {
      case 'ideas':
        return {
          key: 'ideas',
          placeholder: 'Describe your own idea…',
          hint: 'Still not sure about any of these? Write your own idea below.',
        };
      case 'idea':
        return {
          key: 'idea',
          placeholder: 'Tell Curo how to write the script…',
          hint: 'Dump your script idea here if you have something on your mind.',
        };
      case 'script':
        return {
          key: 'script',
          placeholder: 'Ask Curo to change the script…',
          hint: 'Dump your script idea here if you have something on your mind.',
        };
      case 'storyboard':
        return {
          key: 'storyboard',
          placeholder: 'Ask for a different shot…',
          hint: 'Want a different shot? Keep iterating below.',
        };
      case 'caption':
        return {
          key: 'caption',
          placeholder: 'Ask for different captions…',
          hint: 'Dump your caption idea if you have anything on your mind.',
        };
      default:
        return null;
    }
  }
  if (s.tab === 'sim' && s.sim.view === 'result') {
    // The hint points at the biggest thing holding the recording back (logic doc §14).
    const result = cachedSimulation(s.sim.simulationId)?.result;
    const top = result?.audiences[s.sim.audience]?.holding[0]?.short;
    return {
      key: 'sim',
      placeholder: 'Ask Curo about this simulation…',
      hint: top
        ? `Biggest thing holding it back: ${top}. Ask Curo why, or try a what-if.`
        : 'Ask Curo anything about this simulation.',
    };
  }
  return null;
}
