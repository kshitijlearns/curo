'use client';
/** /dev/avatars: every Follower Persona avatar mood, colour, size and state (v2.2 phase 2). */
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { BackHeader } from '@/components/Chrome';
import { PersonaAvatar, type AvatarState } from '@/components/PersonaAvatar';
import { COLORS, MOODS, type Mood } from '@/lib/avatar';

const SEEDS = [20271, 41203, 7719, 93311];
const NAMES = ['The Festive Planner', 'The Budget Stylist', 'The Loyal Fan', 'The Friend Tagger'];
const SHARES = [0.31, 0.27, 0.23, 0.19];
const SIZES = [24, 40, 64, 120] as const;
const STATES: AvatarState[] = ['idle', 'listening', 'thinking', 'loading'];

export default function Avatars() {
  const router = useRouter();
  const [mood, setMood] = useState<Mood>('love');
  const [animated, setAnimated] = useState(true);
  const [seedShift, setSeedShift] = useState(0);
  return (
    <div className="app">
      <BackHeader title="Persona avatars" onBack={() => router.push('/')} sub="Dot-cluster characters: moods, colours, sizes and states." />
      <main className="sheet" style={{ paddingBottom: 64 }}>
        <div className="row wrap" style={{ gap: 8 }}>
          {MOODS.map((m) => (
            <button key={m} className={`pill ${m === mood ? 'blue' : 'white'}`} aria-pressed={m === mood} onClick={() => setMood(m)}>
              {m}
            </button>
          ))}
        </div>
        <div className="row wrap" style={{ gap: 8, marginTop: 10 }}>
          <button className="btn small ghost" aria-pressed={!animated} onClick={() => setAnimated((v) => !v)}>
            {animated ? 'Motion on' : 'Motion off (static shapes)'}
          </button>
          <button className="btn small ghost" onClick={() => setSeedShift((s) => s + 1)}>
            New seeds
          </button>
        </div>

        <h2 style={{ marginTop: 24 }}>The four personas · {mood}</h2>
        <div className="row wrap" style={{ gap: 18, marginTop: 10 }}>
          {COLORS.map((c, i) => (
            <figure key={c} style={{ margin: 0, textAlign: 'center' }}>
              <PersonaAvatar seed={SEEDS[i] + seedShift * 97} color={c} mood={mood} size={120} animated={animated} name={NAMES[i]} share={SHARES[i]} />
              <figcaption className="small">
                {NAMES[i]} · {Math.round(SHARES[i] * 100)}%
              </figcaption>
            </figure>
          ))}
        </div>

        <h2 style={{ marginTop: 24 }}>Every mood</h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th />
                {MOODS.map((m) => (
                  <th key={m} className="small" style={{ padding: '4px 6px' }}>
                    {m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COLORS.map((c, i) => (
                <tr key={c}>
                  <th className="small" style={{ textAlign: 'left', paddingRight: 8 }}>
                    {c}
                  </th>
                  {MOODS.map((m) => (
                    <td key={m} style={{ padding: 4 }}>
                      <PersonaAvatar seed={SEEDS[i] + seedShift * 97} color={c} mood={m} size={64} animated={animated} name={NAMES[i]} share={SHARES[i]} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h2 style={{ marginTop: 24 }}>Sizes</h2>
        <div className="row" style={{ gap: 16, alignItems: 'end' }}>
          {SIZES.map((s) => (
            <figure key={s} style={{ margin: 0, textAlign: 'center' }}>
              <PersonaAvatar seed={SEEDS[0] + seedShift * 97} color="blue" mood={mood} size={s} animated={animated} name={NAMES[0]} share={SHARES[0]} />
              <figcaption className="small">{s}px</figcaption>
            </figure>
          ))}
        </div>

        <h2 style={{ marginTop: 24 }}>Studio states</h2>
        <div className="row wrap" style={{ gap: 16 }}>
          {STATES.map((st) => (
            <figure key={st} style={{ margin: 0, textAlign: 'center' }}>
              <PersonaAvatar seed={SEEDS[1] + seedShift * 97} color="lavender" mood={mood} state={st} size={40} animated={animated} name={NAMES[1]} share={SHARES[1]} />
              <figcaption className="small">{st}</figcaption>
            </figure>
          ))}
        </div>

        <h2 style={{ marginTop: 24 }}>On the dark recap slide</h2>
        <div className="row wrap" style={{ gap: 16, background: 'var(--ink)', padding: 16, borderRadius: 20 }}>
          {COLORS.map((c, i) => (
            <PersonaAvatar key={c} seed={SEEDS[i] + seedShift * 97} color={c} mood={mood} size={64} animated={animated} name={NAMES[i]} share={SHARES[i]} surface="dark" />
          ))}
        </div>
        <p className="small muted" style={{ marginTop: 16 }}>
          Built from your public comments. Personas are summaries, not real people.
        </p>
      </main>
    </div>
  );
}
