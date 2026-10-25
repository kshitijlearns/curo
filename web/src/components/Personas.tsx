'use client';
/**
 * Follower Personas in the app (v2.2): Home's cards and detail sheet, persona chat, the Studio
 * persona row with its popovers, and the "Who this is for" list. Every surface carries the
 * label "Built from your public comments. Personas are summaries, not real people."
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useRef, useState } from 'react';

import { Section } from './Carousel';
import { Icon } from './Icon';
import { Overlay } from './Overlay';
import { AvatarSkeleton, PersonaAvatar } from './PersonaAvatar';
import { api, personaChatStream, type S } from '@/lib/api';
import type { Mood, PersonaColor } from '@/lib/avatar';
import { usePersona, usePersonaChatHistory, usePersonaReactions, usePersonas } from '@/lib/hooks';
import { useApp } from '@/state/app';

export const PERSONA_LABEL = 'Built from your public comments. Personas are summaries, not real people.';
const EARLY = 'Early guess: gets sharper as people comment';

type Card = S['PersonaCard'];
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
export function MoodMeter({ meter }: { meter: number }) {
  return (
    <div className="meter" role="meter" aria-valuemin={1} aria-valuemax={5} aria-valuenow={meter} aria-valuetext={METER_WORDS[meter - 1]} aria-label="How they feel about your recent reels">
      <div className="meter-steps" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((i) => (
          <i key={i} className={i <= meter ? 'on' : ''} />
        ))}
      </div>
      <span className="small">{METER_WORDS[meter - 1]}</span>
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
    <span className={`badge badge-${badge.toLowerCase()}`}>
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

export function PersonaSection() {
  const q = usePersonas();
  const [open, setOpen] = useState<string | null>(null);
  const start = useStartProject();
  const title = 'What your followers think of you';
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
  if (q.isLoading || q.data?.status === 'building') {
    return (
      <Section title={title}>
        {[1, 2].map((i) => (
          <div key={i} className="card persona-card skeleton-card" aria-label="Building your follower personas">
            <div className="row" style={{ gap: 12 }}>
              <AvatarSkeleton size={64} seed={i * 7919} />
              <div>
                <h3>Meeting your followers…</h3>
                <p className="small muted">Your follower personas are being built from your comments.</p>
              </div>
            </div>
          </div>
        ))}
      </Section>
    );
  }
  if (q.error || !q.data) return <Section title={title} error={q.error ?? 'x'} onRetry={() => q.refetch()}>{null}</Section>;
  const d = q.data;
  return (
    <>
      <Section
        title={title}
        intro={
          <>
            {d.summary ? <p className="persona-summary">{d.summary}</p> : null}
            {d.early_guess ? <p className="persona-summary small">{EARLY}. Post and reply to comments to sharpen them.</p> : null}
          </>
        }
        footer={<PersonaLabel style={{ margin: '4px 6px 0' }} />}
      >
        {(d.personas ?? []).map((p) => (
          <PersonaCardView key={p.id} p={p} onOpen={() => setOpen(p.id)} onMake={(idea) => start.mutate({ idea, persona: p.id })} busy={start.isPending} />
        ))}
      </Section>
      {open ? <PersonaSheet id={open} onClose={() => setOpen(null)} /> : null}
    </>
  );
}

export function PersonaCardView({ p, onOpen, onMake, busy }: { p: Card; onOpen: () => void; onMake: (idea: string) => void; busy?: boolean }) {
  return (
    <article className="card persona-card">
      <button className="persona-top" onClick={onOpen} aria-label={`${p.name}: open details`}>
        <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={64} name={p.name} share={p.share} />
        <div style={{ minWidth: 0, textAlign: 'left' }}>
          <h3 style={{ margin: 0 }}>{p.name}</h3>
          <div className="row" style={{ gap: 8, marginTop: 6 }}>
            <span className="pill white">{p.share_pct}% of comments</span>
            <ConfidenceDots level={p.confidence} />
          </div>
        </div>
      </button>
      {p.is_starter ? <span className="pill lav early">Early guess</span> : null}
      <blockquote className="thought">“{p.thought.thought}”</blockquote>
      <MoodMeter meter={p.meter} />
      <p className="small muted" style={{ margin: '10px 0 4px' }}>
        Loves
      </p>
      <div className="row wrap" style={{ gap: 6 }}>
        {(p.thought.loves ?? []).slice(0, 2).map((l) => (
          <span key={l} className="pill lav">
            {l}
          </span>
        ))}
      </div>
      {(p.thought.wants_more ?? []).length ? (
        <>
          <p className="small muted" style={{ margin: '10px 0 4px' }}>
            Wants more of
          </p>
          <div className="stack" style={{ gap: 6 }}>
            {(p.thought.wants_more ?? []).slice(0, 2).map((w) => (
              <div key={w} className="row between want">
                <span className="small">{w}</span>
                <button className="link small" disabled={busy} onClick={() => onMake(w)} aria-label={`Make this: ${w}`}>
                  Make this <Icon name="arrowRight" size={14} />
                </button>
              </div>
            ))}
          </div>
        </>
      ) : null}
      <p className="small muted" style={{ marginTop: 12 }}>
        {p.evidence_line}
      </p>
    </article>
  );
}

// ---------------------------------------------------------------------- detail sheet

export function PersonaSheet({ id, onClose, context = 'home', contextId = null }: { id: string; onClose: () => void; context?: 'home' | 'studio' | 'simulator'; contextId?: string | null }) {
  const q = usePersona(id);
  const p = q.data;
  const [chat, setChat] = useState(context !== 'home');
  const titleId = useId();
  return (
    <Overlay labelledBy={titleId} onClose={onClose}>
      <div className="persona-sheet">
        <div className="row between">
          <span className="small muted">Follower persona</span>
          <button className="circle sm" onClick={onClose} aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </div>
        {!p ? (
          <div className="row" style={{ gap: 12, marginTop: 12 }}>
            <AvatarSkeleton size={120} />
          </div>
        ) : (
          <>
            <div className="persona-hero">
              <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={p.mood as Mood} size={120} name={p.name} share={p.share} />
              <div>
                <h2 id={titleId} style={{ margin: 0, fontSize: 24 }}>
                  {p.name}
                </h2>
                <p className="light" style={{ margin: '4px 0 8px' }}>
                  {p.tagline}
                </p>
                <div className="row" style={{ gap: 8 }}>
                  <span className="pill white">{p.share_pct}% of your comments</span>
                  <ConfidenceDots level={p.confidence} />
                </div>
              </div>
            </div>
            {p.is_starter ? <p className="pill lav early">{EARLY}</p> : null}
            <blockquote className="thought">“{p.thought.thought}”</blockquote>
            <MoodMeter meter={p.meter} />
            <Block title="What they come for">
              <ul className="plain">{p.comes_for.map((c) => <li key={c}>{c}</li>)}</ul>
            </Block>
            <Block title="What they love">
              <Traits items={p.loves} />
            </Block>
            <Block title="What makes them scroll past">
              <Traits items={p.turn_offs} />
            </Block>
            <Block title="How they engage">
              <p>{p.engagement_style}</p>
              {p.places?.length ? <p className="small muted">They mention {p.places.join(' and ')}.</p> : null}
            </Block>
            {p.favourite_reels?.length ? (
              <Block title="Their favourite reels">
                <div className="fav-reels">
                  {p.favourite_reels.map((r) => (
                    <div key={r.id} className={`fav tone-${r.tone}`}>
                      <span className="small">{r.title}</span>
                      <span className="small muted">{r.comments} of their comments</span>
                    </div>
                  ))}
                </div>
              </Block>
            ) : null}
            <Block title="A typical comment">
              <p>“{p.typical_comment}”</p>
              <p className="small muted">Paraphrased from many comments, never a real one.</p>
            </Block>
            <Block title="Language mix">
              <p>{p.language.map((l) => (l.share !== null && l.share !== undefined ? `${l.name} ${Math.round(l.share * 100)}%` : l.name)).join(', ')}</p>
            </Block>
            {(p.history ?? []).length > 1 ? (
              <Block title="Over time">
                <div className="history">
                  {(p.history ?? []).map((h) => (
                    <div key={h.period} className="hist">
                      <PersonaAvatar seed={p.avatar_seed} color={p.color as PersonaColor} mood={h.mood as Mood} size={24} decorative animated={false} />
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
                <button className="btn small" onClick={() => setChat(true)}>
                  <Icon name="comments" size={16} /> Ask them something
                </button>
              )}
            </Block>
            <PersonaLabel style={{ marginTop: 16 }} />
          </>
        )}
      </div>
    </Overlay>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="persona-block">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function Traits({ items }: { items: S['PersonaTrait'][] }) {
  return (
    <ul className="plain">
      {items.map((t) => (
        <li key={t.text}>
          {t.text}
          {t.evidence ? <span className="small muted evidence">{t.evidence}</span> : null}
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
        <button className="circle sm blue" type="submit" disabled={busy || !text.trim()} aria-label="Send">
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
