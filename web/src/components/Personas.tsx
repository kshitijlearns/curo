'use client';
/**
 * Follower Personas in the app (v2.2, v3 look): Home's podium, ranking and "They want more of"
 * rows, the detail sheet, persona chat, the Studio persona row with its popovers, and the
 * "Who this is for" list. Every surface carries the
 * label "Built from your public comments. Personas are summaries, not real people."
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useRef, useState } from 'react';

import { Icon } from './Icon';
import { Overlay } from './Overlay';
import { AvatarSkeleton, PersonaAvatar } from './PersonaAvatar';
import { api, personaChatStream, type S } from '@/lib/api';
import type { Mood, PersonaColor } from '@/lib/avatar';
import { blockAt, PERSONA_BLOCK } from '@/lib/palette';
import { usePersona, usePersonaChatHistory, usePersonaReactions, usePersonas } from '@/lib/hooks';
import { useApp } from '@/state/app';

export const PERSONA_LABEL = 'Built from your public comments. Personas are summaries, not real people.';
const EARLY = 'Early guess: gets sharper as people comment';

type Reaction = S['PersonaReactionOut'];

export function PersonaLabel({ style }: { style?: React.CSSProperties }) {
  return (
    <p className="small muted persona-label" style={style}>
      {PERSONA_LABEL}
    </p>
  );
}

/** How much data backs a persona: 1–3 filled dots. */
export function ConfidenceDots({ level }: { level: 'low' | 'medium' | 'high' }) {
  const n = { low: 1, medium: 2, high: 3 }[level];
  return (
    <span className="conf-dots" role="img" aria-label={`Confidence: ${level}`} title={`Confidence: ${level}`}>
      {[1, 2, 3].map((i) => (
        <i key={i} className={i <= n ? 'on' : ''} />
      ))}
    </span>
  );
}

const METER_WORDS = ['Not feeling it', 'Lukewarm', 'Interested', 'Fan', 'Big fan'];

/** The 5-step mood meter, labelled in words (not just colour). */
export function MoodMeter({ meter, compact = false }: { meter: number; compact?: boolean }) {
  return (
    <div className={`meter${compact ? ' compact' : ''}`} role="meter" aria-valuemin={1} aria-valuemax={5} aria-valuenow={meter} aria-valuetext={METER_WORDS[meter - 1]} aria-label="How they feel about your recent reels">
      <div className="meter-steps" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => (
          <i key={i} className={i <= meter ? 'on' : ''} />
        ))}
      </div>
      <span className="meter-word">{METER_WORDS[meter - 1]}</span>
    </div>
  );
}

/** A reaction's badge: CURO's own small glyph + the word. */
export function ReactionBadge({ badge }: { badge: 'Love' | 'Like' | 'Unsure' | 'Skip' }) {
  const glyph = {
    Love: <path d="M8 13.5S2.5 10.2 2.5 6.6C2.5 4.9 3.8 3.6 5.4 3.6c1.1 0 2 .6 2.6 1.5.6-.9 1.5-1.5 2.6-1.5 1.6 0 2.9 1.3 2.9 3 0 3.6-5.5 6.9-5.5 6.9z" fill="currentColor" />,
    Like: <path d="M3 9.5l3.2 3.2L13 5.5" stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />,
    Unsure: <path d="M2.5 9c1.4-2 2.8-2 4.1 0s2.7 2 4.1 0 2.4-1.6 2.8-.9" stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" />,
    Skip: <path d="M3 8h9M9 4.5L12.5 8 9 11.5" stroke="currentColor" strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />,
  }[badge];
  return (
    <span className={`react-badge react-badge-${badge.toLowerCase()}`}>
      <svg width={12} height={12} viewBox="0 0 16 16" aria-hidden="true">
        {glyph}
      </svg>
      {badge}
    </span>
  );
}

function useStartProject() {
  const s = useApp();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ idea }: { idea: string; persona: string }) => api<S['ProjectStarted']>('/projects', { body: { idea_text: idea } }),
    onSuccess: (r, v) => {
      qc.invalidateQueries({ queryKey: ['me'] });
      s.setFocusPersona(v.persona);
      s.openProject(r.project_id);
    },
  });
}

// ---------------------------------------------------------------------- Home

/** Podium order for four: second, first, third, fourth (by share), like a leaderboard. */
const PODIUM = [1, 0, 2, 3];

/**
 * Home's hero (v3): the four personas on a podium — bar height is each group's share of your
 * comments — then a dark card ranking them, with how each one feels in words. Tap any of them
 * for the detail sheet.
 */
export function PersonaPodium() {
  const q = usePersonas();
  const [open, setOpen] = useState<string | null>(null);
  // A persona tapped on the recap's summary slide opens here once the recap closes.
  useEffect(() => {
    if (q.data?.status !== 'ready') return;
    try {
      const id = sessionStorage.getItem('curo.openPersona');
      if (id) {
        sessionStorage.removeItem('curo.openPersona');
        if (q.data.personas?.some((p) => p.id === id)) setOpen(id);
      }
    } catch {
      /* private mode */
    }
  }, [q.data]);
  const title = 'Your followers';
  const cards = [...(q.data?.personas ?? [])].sort((x, y) => y.share - x.share);
  const ready = q.data?.status === 'ready' && cards.length >= 1;
  if (q.error) {
    return (
      <section aria-label={title}>
        <SectionHead title={title} />
        <div className="card coral" role="alert">
          <p>This section didn’t load.</p>
          <button className="btn small" style={{ marginTop: 10 }} onClick={() => q.refetch()}>
            Try again
          </button>
        </div>
      </section>
    );
  }
  const max = Math.max(...cards.map((c) => c.share), 0.01);
  return (
    <section aria-label={title} className="followers">
      <SectionHead title={title} hint={ready ? 'by share of comments' : undefined} />
      <div className="podium">
        {(ready ? PODIUM.filter((i) => i < cards.length) : [1, 0, 2, 3]).map((rank) => {
          const p = ready ? cards[rank] : undefined;
          const h = p ? 74 + Math.round((p.share / max) * 108) : [150, 182, 128, 104][rank];
          const block = p ? PERSONA_BLOCK[p.color] ?? 'paper' : 'paper';
          return (
            <div key={rank} className="podium-col" style={{ ['--h' as string]: `${h}px`, ['--i' as string]: rank }}>
              {p ? (
                <button className="podium-top" onClick={() => setOpen(p.id)} aria-label={`${p.name}: open details`}>
                  <span className="podium-rank">{ordinal(rank + 1)}</span>
                  <span className="podium-name">{p.short_name}</span>
                  <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={rank === 0 ? 64 : 52} name={p.name} share={p.share} />
                </button>
              ) : (
                <div className="podium-top">
                  <AvatarSkeleton size={rank === 0 ? 64 : 52} seed={(rank + 1) * 7919} />
                </div>
              )}
              <div className={`podium-bar blk-${block}`}>
                {p ? <span className="podium-pct">{p.share_pct}%</span> : null}
              </div>
            </div>
          );
        })}
      </div>
      <div className="rank-card">
        <p className="rank-summary">{ready ? (q.data?.summary ?? EARLY) : 'Meeting your followers…'}</p>
        {ready ? (
          <div className="stack" style={{ gap: 8 }}>
            {cards.map((p, i) => (
              <button key={p.id} className="rank-row" onClick={() => setOpen(p.id)} aria-label={`${p.name}, ${p.meter_word}: open details`}>
                <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={40} decorative animated={false} />
                <span className="rank-main">
                  <small>{ordinal(i + 1)}</small>
                  <strong>{p.name}</strong>
                </span>
                <MoodMeter meter={p.meter} compact />
              </button>
            ))}
          </div>
        ) : (
          <p className="small" style={{ opacity: 0.7, margin: 0 }}>
            Your follower personas are being built from your comments.
          </p>
        )}
        {q.data?.early_guess ? <p className="small" style={{ opacity: 0.7, margin: '10px 4px 0' }}>Early guess: post and reply to comments to sharpen them.</p> : null}
        <PersonaLabel style={{ margin: '12px 4px 0', color: 'rgba(255,255,255,.6)' }} />
      </div>
      {open ? <PersonaSheet id={open} onClose={() => setOpen(null)} /> : null}
    </section>
  );
}

/** "They want more of": each persona's asks as rows, one tap starts a Studio project. */
export function WantsPanel() {
  const q = usePersonas();
  const start = useStartProject();
  if (q.data?.status !== 'ready') return null;
  const rows = (q.data.personas ?? []).flatMap((p) => (p.thought.wants_more ?? []).slice(0, 2).map((w) => ({ p, w })));
  if (!rows.length) return null;
  return (
    <section aria-label="They want more of">
      <SectionHead title="They want more of" />
      <div className="panel-block pink">
        {rows.slice(0, 6).map(({ p, w }) => (
          <div key={`${p.id}-${w}`} className="pill-row">
            <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={34} decorative animated={false} />
            <span className="pill-row-main">
              <strong>{w}</strong>
              <small>{p.short_name}</small>
            </span>
            <button className="arrow dark" disabled={start.isPending} onClick={() => start.mutate({ idea: w, persona: p.id })} aria-label={`Make this: ${w}`}>
              <Icon name="arrowUpRight" size={18} strokeWidth={2.2} />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

/** A section title in the big type, with an optional quiet hint or action on the right. */
export function SectionHead({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="section-head">
      <h2>{title}</h2>
      {action ?? (hint ? <span className="hint">{hint}</span> : null)}
    </div>
  );
}

export const ordinal = (n: number) => `${n}${n === 1 ? 'st' : n === 2 ? 'nd' : n === 3 ? 'rd' : 'th'}`;

// ---------------------------------------------------------------------- detail sheet

export function PersonaSheet({ id, onClose, context = 'home', contextId = null }: { id: string; onClose: () => void; context?: 'home' | 'studio' | 'simulator'; contextId?: string | null }) {
  const q = usePersona(id);
  const p = q.data;
  const [chat, setChat] = useState(context !== 'home');
  const titleId = useId();
  const block = p ? PERSONA_BLOCK[p.color] ?? 'paper' : 'paper';
  return (
    <Overlay labelledBy={titleId} onClose={onClose}>
      <div className="persona-sheet">
        {!p ? (
          <div className="row between">
            <AvatarSkeleton size={120} />
            <button className="circle" onClick={onClose} aria-label="Close">
              <Icon name="close" size={18} />
            </button>
          </div>
        ) : (
          <>
            <div className={`persona-hero blk-${block}`}>
              <div className="row between" style={{ alignItems: 'flex-start' }}>
                <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={104} name={p.name} share={p.share} />
                <button className="circle white" onClick={onClose} aria-label="Close">
                  <Icon name="close" size={18} />
                </button>
              </div>
              <span className="eyebrow">Follower persona</span>
              <h2 id={titleId} className="block-title">
                {p.name}
              </h2>
              <p className="persona-tagline">{p.tagline}</p>
              <div className="row wrap" style={{ gap: 8 }}>
                <span className="chip white">{p.share_pct}% of your comments</span>
                <span className="chip white">
                  <ConfidenceDots level={p.confidence} /> {p.confidence} confidence
                </span>
              </div>
            </div>
            {p.is_starter ? <p className="chip ink early">{EARLY}</p> : null}
            <blockquote className="thought">“{p.thought.thought}”</blockquote>
            <MoodMeter meter={p.meter} />
            <Block title="What they come for">
              <div className="row wrap" style={{ gap: 6 }}>
                {p.comes_for.map((c) => (
                  <span key={c} className="chip outline">
                    {c}
                  </span>
                ))}
              </div>
            </Block>
            <div className="trait-grid">
              <Block title="Loves" tone="lime">
                <Traits items={p.loves} sign="+" />
              </Block>
              <Block title="Scrolls past" tone="coral">
                <Traits items={p.turn_offs} sign="–" />
              </Block>
            </div>
            <Block title="How they engage">
              <p style={{ margin: 0 }}>{p.engagement_style}</p>
              {p.places?.length ? <p className="small muted" style={{ marginTop: 6 }}>They mention {p.places.join(' and ')}.</p> : null}
            </Block>
            {p.favourite_reels?.length ? (
              <Block title="Their favourite reels">
                <div className="fav-reels">
                  {p.favourite_reels.map((r, i) => (
                    <div key={r.id} className={`fav blk-${blockAt(i + 1)}`}>
                      <Icon name="play" size={16} />
                      <span className="fav-title">{r.title}</span>
                      <span className="fav-n">{r.comments} comments</span>
                    </div>
                  ))}
                </div>
              </Block>
            ) : null}
            <Block title="A typical comment">
              <div className="comment-bubble">
                <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={28} decorative animated={false} />
                <p>“{p.typical_comment}”</p>
              </div>
              <p className="small muted" style={{ marginTop: 6 }}>
                Paraphrased from many comments, never a real one.
              </p>
            </Block>
            <Block title="Language mix">
              <div className="lang-bar" aria-hidden="true">
                {p.language.map((l, i) => (
                  <i key={l.name} className={`blk-${blockAt(i)}`} style={{ flex: l.share ?? 1 / p.language.length }} />
                ))}
              </div>
              <p className="small" style={{ marginTop: 8 }}>
                {p.language.map((l) => (l.share !== null && l.share !== undefined ? `${l.name} ${Math.round(l.share * 100)}%` : l.name)).join(' · ')}
              </p>
            </Block>
            {(p.history ?? []).length > 1 ? (
              <Block title="Over time">
                <div className="history">
                  {(p.history ?? []).map((h) => (
                    <div key={h.period} className="hist">
                      <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={h.mood as Mood} size={28} decorative animated={false} />
                      <span className="small">{new Date(h.period).toLocaleDateString('en-IN', { month: 'short' })}</span>
                      <span className="small muted">{Math.round(h.share * 100)}%</span>
                    </div>
                  ))}
                </div>
              </Block>
            ) : null}
            <Block title={`Chat with ${p.short_name}`}>
              {chat ? (
                <PersonaChat personaId={p.id} name={p.short_name} context={context} contextId={contextId} />
              ) : (
                <button className="btn small ink" onClick={() => setChat(true)}>
                  <Icon name="comments" size={16} /> Ask them something
                </button>
              )}
            </Block>
            <p className="small muted" style={{ margin: '14px 4px 0' }}>
              {p.evidence_line}
            </p>
            <PersonaLabel style={{ marginTop: 6 }} />
          </>
        )}
      </div>
    </Overlay>
  );
}

function Block({ title, children, tone }: { title: string; children: React.ReactNode; tone?: 'lime' | 'coral' }) {
  return (
    <section className={`persona-block${tone ? ` tone-${tone}` : ''}`}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function Traits({ items, sign }: { items: S['PersonaTrait'][]; sign: string }) {
  return (
    <ul className="traits">
      {items.map((t) => (
        <li key={t.text}>
          <i aria-hidden="true">{sign}</i>
          <span>
            {t.text}
            {t.evidence ? <span className="small muted evidence">{t.evidence}</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------- chat (T28)

const SUGGESTIONS = ['Why do you scroll past?', 'What would make you share a reel?', 'What do you want next?'];

export function PersonaChat({ personaId, name, context, contextId }: { personaId: string; name: string; context: 'home' | 'studio' | 'simulator'; contextId: string | null }) {
  const history = usePersonaChatHistory(personaId, context, contextId);
  const [live, setLive] = useState<{ role: string; content: string }[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const send = async (q: string) => {
    if (!q.trim() || busy) return;
    setBusy(true);
    setText('');
    setLive((l) => [...l, { role: 'user', content: q }, { role: 'persona', content: '' }]);
    try {
      for await (const ev of personaChatStream(personaId, { message: q, context_type: context, context_id: contextId })) {
        if (ev.event === 'delta') {
          setLive((l) => [...l.slice(0, -1), { role: 'persona', content: l[l.length - 1].content + ev.data.text }]);
        } else if (ev.event === 'done') {
          setLive((l) => [...l.slice(0, -1), { role: 'persona', content: ev.data.text }]);
        } else if (ev.event === 'error') {
          setLive((l) => [...l.slice(0, -1), { role: 'persona', content: ev.data.message ?? 'Couldn’t answer just now.' }]);
        }
      }
    } finally {
      setBusy(false);
      qc.invalidateQueries({ queryKey: ['billing'] });
    }
  };
  const past = (history.data ?? []).map((m) => ({ role: m.role, content: m.content }));
  const all = [...past, ...live];
  return (
    <div className="persona-chat">
      <div className="stack" style={{ gap: 8 }} aria-live="polite">
        {all.map((m, i) => (
          <div key={i} className={`bubble ${m.role === 'user' ? 'me' : 'them'}`}>
            {m.content || '…'}
          </div>
        ))}
      </div>
      {all.length === 0 ? (
        <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
          {SUGGESTIONS.map((q) => (
            <button key={q} className="pill white" onClick={() => send(q)} disabled={busy}>
              {q}
            </button>
          ))}
        </div>
      ) : null}
      <form
        className="row"
        style={{ gap: 8, marginTop: 10 }}
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <label className="sr-only" htmlFor={`pc-${personaId}`}>
          Ask {name}
        </label>
        <input id={`pc-${personaId}`} className="field" style={{ height: 44 }} value={text} onChange={(e) => setText(e.target.value)} placeholder={`Ask ${name}…`} maxLength={500} disabled={busy} />
        <button className="circle sm violet" type="submit" disabled={busy || !text.trim()} aria-label="Send">
          <Icon name="send" size={18} />
        </button>
      </form>
      <p className="small muted" style={{ marginTop: 6 }}>
        Each message counts towards your Ask Curo messages.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------- Studio: the persona row

/** Above the Studio composer on every step: listening while the creator types, thinking while
 *  a draft is scored, then each persona's own mood and reaction. Tap → that persona's take. */
export function PersonaRow() {
  const s = useApp();
  const personas = usePersonas();
  const t = s.personaTarget;
  const fetched = usePersonaReactions(t?.reactions ? null : (t?.projectId ?? null), t?.key ?? null, t?.target);
  const data = t?.reactions ?? fetched.data;
  const [open, setOpen] = useState<string | null>(null);
  const opener = useRef<HTMLButtonElement | null>(null);

  // "Make this" from a Home card: that persona is preselected once its take is in.
  useEffect(() => {
    if (s.focusPersona && data?.reactions?.some((r) => r.persona_id === s.focusPersona)) {
      setOpen(s.focusPersona);
      s.setFocusPersona(null);
    }
  }, [s, data]);

  const cards = personas.data?.personas ?? [];
  if (personas.data?.status !== 'ready' || cards.length < 4) {
    return (
      <div className="persona-row" aria-label="Your follower personas are being built">
        <div className="persona-row-inner">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="persona-slot">
              <AvatarSkeleton size={40} seed={i * 4099} />
            </div>
          ))}
        </div>
        <p className="small muted persona-row-note">Your follower personas are being built…</p>
      </div>
    );
  }
  const byId = new Map((data?.reactions ?? []).map((r) => [r.persona_id, r]));
  const thinking = s.composer?.busy || (fetched.isFetching && !t?.reactions);
  const state = s.typing ? 'listening' : thinking ? 'thinking' : 'idle';
  const current = open ? byId.get(open) : undefined;
  return (
    <div className="persona-row" role="group" aria-label="Your follower personas">
      {data?.summary && state === 'idle' ? <p className="small persona-row-note">{data.summary}</p> : null}
      {cards[0]?.is_starter ? <p className="small muted persona-row-note">Early guess</p> : null}
      <div className="persona-row-inner">
        {cards.map((p) => {
          const r = byId.get(p.id);
          const mood = (r?.mood ?? 'neutral') as Mood;
          return (
            <button
              key={p.id}
              className={`persona-slot${open === p.id ? ' active' : ''}`}
              title={p.name}
              aria-label={`${p.name}${r ? `: ${r.reaction_label}` : ''}. Open their take`}
              aria-expanded={open === p.id}
              disabled={!r}
              onClick={(e) => {
                opener.current = e.currentTarget;
                setOpen(open === p.id ? null : p.id);
              }}
            >
              <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={mood} state={state} size={40} name={p.name} share={p.share} decorative />
              <span className="persona-name">{p.short_name}</span>
              {r && state === 'idle' ? <ReactionBadge badge={r.badge} /> : null}
            </button>
          );
        })}
      </div>
      {current ? (
        <PersonaPopover
          r={current}
          onClose={() => {
            setOpen(null);
            opener.current?.focus();
          }}
          onApply={(text) => {
            setOpen(null);
            s.composer?.onSend(text);
          }}
          projectId={t?.projectId ?? null}
        />
      ) : null}
    </div>
  );
}

function PersonaPopover({ r, onClose, onApply, projectId }: { r: Reaction; onClose: () => void; onApply: (text: string) => void; projectId: string | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const [ask, setAsk] = useState(false);
  useEffect(() => {
    const first = ref.current?.querySelector<HTMLElement>('button, [href], input');
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
      if (e.key === 'Tab' && ref.current) {
        // Keep focus inside the popover while it's open.
        const items = Array.from(ref.current.querySelectorAll<HTMLElement>('button, [href], input'));
        if (!items.length) return;
        const i = items.indexOf(document.activeElement as HTMLElement);
        if (e.shiftKey && i <= 0) {
          e.preventDefault();
          items[items.length - 1].focus();
        } else if (!e.shiftKey && i === items.length - 1) {
          e.preventDefault();
          items[0].focus();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const would = r.would as S['PersonaWould'];
  return (
    <>
      <div className="popover-scrim" onClick={onClose} aria-hidden="true" />
      <div ref={ref} className="persona-pop" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="row between">
          <div className="row" style={{ gap: 10 }}>
            <PersonaAvatar seed={r.avatar_seed} color={r.color as PersonaColor} mood={r.mood as Mood} size={40} name={r.name} share={r.share} />
            <div>
              <h3 id={titleId} style={{ margin: 0, fontSize: 16 }}>
                {r.name}
              </h3>
              <span className="small muted">{Math.round(r.share * 100)}% of your comments</span>
            </div>
          </div>
          <button className="circle sm" onClick={onClose} aria-label="Close">
            <Icon name="close" size={16} />
          </button>
        </div>
        <div className="row between" style={{ marginTop: 12 }}>
          <span className="pop-reaction">{r.reaction_label}</span>
          <span className="score" style={{ fontSize: 22 }} aria-label={`Persona score ${r.score} of 100`}>
            {r.score}
            <span className="small muted">/100</span>
          </span>
        </div>
        <div className="row wrap" style={{ gap: 6, marginTop: 10 }} aria-label="Would they…">
          {(['like', 'comment', 'share', 'save'] as const).map((k) => (
            <span key={k} className={`would ${would[k] ? 'yes' : 'no'}`}>
              {would[k] ? '✓' : '✗'} {k}
              {k === 'save' ? <em> (simulated)</em> : null}
            </span>
          ))}
        </div>
        <p className="small muted" style={{ margin: '12px 0 2px' }}>
          In their words
        </p>
        <p>“{r.opinion}”</p>
        {r.win_them_over ? (
          <div className="card lav" style={{ margin: '10px 0 0', padding: 12 }}>
            <p className="small muted" style={{ margin: 0 }}>
              One change that would win them over
            </p>
            <p style={{ margin: '4px 0 8px' }}>{r.win_them_over}</p>
            <button className="btn small" onClick={() => onApply(r.win_them_over as string)}>
              Apply
            </button>
          </div>
        ) : null}
        {r.evidence?.length ? (
          <>
            <p className="small muted" style={{ margin: '12px 0 4px' }}>
              Why we think so
            </p>
            <div className="stack" style={{ gap: 4 }}>
              {r.evidence.map((e) => (
                <span key={e} className="evidence-chip small">
                  {e}
                </span>
              ))}
            </div>
          </>
        ) : null}
        {ask ? (
          <div style={{ marginTop: 12 }}>
            <PersonaChat personaId={r.persona_id} name={r.short_name} context="studio" contextId={projectId} />
          </div>
        ) : (
          <button className="btn small ghost" style={{ marginTop: 12 }} onClick={() => setAsk(true)}>
            <Icon name="comments" size={16} /> Ask more
          </button>
        )}
        <PersonaLabel style={{ marginTop: 10 }} />
      </div>
    </>
  );
}

/** "Who this is for": each persona's reaction to the final draft (or a validated idea). */
export function WhoThisIsFor({ data, title = 'Who this is for' }: { data: S['PersonaReactionsOut'] | null | undefined; title?: string }) {
  if (!data?.reactions?.length) return null;
  return (
    <section className="card who" aria-label={title}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {data.summary ? <p className="small">{data.summary}</p> : null}
      <ul className="plain">
        {data.reactions.map((r) => (
          <li key={r.persona_id} className="row" style={{ gap: 10 }}>
            <PersonaAvatar seed={r.avatar_seed} color={r.color as PersonaColor} mood={r.mood as Mood} size={24} name={r.name} share={r.share} animated={false} />
            <span style={{ flex: 1 }}>{r.name}</span>
            <ReactionBadge badge={r.badge} />
          </li>
        ))}
      </ul>
      <PersonaLabel />
    </section>
  );
}
