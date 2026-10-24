'use client';
/**
 * The Creator Recap story player (v2.1 §3.2): full screen (a phone-width column on desktop),
 * segmented progress bars, tap right / left, press and hold to pause, ← → and space, swipe
 * down or ✕ to close. Slides auto-advance (6 s, 8 s for longer ones); with reduced motion
 * there's no auto-advance and no count-up. "ⓘ How we got this" shows the facts and formula.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import { Icon } from './Icon';
import { apiText, type S } from '@/lib/api';

const COLOURS: Record<string, string> = {
  blue: '#5B73F2',
  lavender: '#C3BFF2',
  pink: '#F2D4E2',
  white: '#FFFFFF',
  gray: '#E4E4EC',
  ink: '#242424',
};
const PALETTE = ['#5B73F2', '#C3BFF2', '#F2D4E2', '#FFFFFF', '#E4E4EC'];

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const m = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(m.matches);
    const on = () => setReduced(m.matches);
    m.addEventListener('change', on);
    return () => m.removeEventListener('change', on);
  }, []);
  return reduced;
}

/** Indian grouping, as the API formats it. */
export function fmtIn(n: number) {
  return Math.round(n).toLocaleString('en-IN');
}

function CountUp({ to, reduced, format = fmtIn }: { to: number; reduced: boolean; format?: (n: number) => string }) {
  const [v, setV] = useState(reduced ? to : 0);
  useEffect(() => {
    if (reduced) return setV(to);
    let raf = 0;
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / 1200);
      setV(to * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to, reduced]);
  return <span className="big">{format(v)}</span>;
}

function Confetti() {
  const bits = useMemo(
    () =>
      Array.from({ length: 26 }, (_, i) => ({
        left: (i * 37) % 100,
        delay: (i % 7) * 0.12,
        colour: PALETTE[i % PALETTE.length],
        round: i % 3 === 0,
      })),
    [],
  );
  return (
    <div className="confetti" aria-hidden="true">
      {bits.map((b, i) => (
        <i key={i} style={{ left: `${b.left}%`, animationDelay: `${b.delay}s`, background: b.colour, borderRadius: b.round ? 6 : 2 }} />
      ))}
    </div>
  );
}

type Slide = S['RecapSlide'];

function Body({
  slide,
  recap,
  reduced,
  accent,
  onClose,
}: {
  slide: Slide;
  recap: S['Recap'];
  reduced: boolean;
  accent: string;
  onClose: () => void;
}) {
  const f = slide.facts as Record<string, any>;
  const copy = slide.copy;
  const head = <h2>{copy.headline}</h2>;
  const sub = copy.subline ? <p className="sub">{copy.subline}</p> : null;
  switch (slide.slide_id) {
    case 'posting':
      return (
        <>
          <CountUp to={f.reels} reduced={reduced} format={(n) => String(Math.round(n))} />
          {head}
          {sub}
          {Array.isArray(f.chart) ? (
            <div className="story-bars-chart" aria-label="Reels per weekday, Monday to Sunday">
              {(f.chart as number[]).map((n, k) => (
                <div
                  key={k}
                  style={{ height: `${Math.max(6, (n / Math.max(1, ...f.chart)) * 100)}%`, background: accent, animationDelay: reduced ? '0s' : `${k * 60}ms` }}
                  title={['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][k]}
                />
              ))}
            </div>
          ) : null}
        </>
      );
    case 'views_total':
      return (
        <>
          <CountUp to={f.views} reduced={reduced} />
          {head}
          {sub}
        </>
      );
    case 'streak':
      return (
        <>
          <CountUp to={f.weeks} reduced={reduced} format={(n) => `${Math.round(n)} weeks`} />
          {head}
          {sub}
        </>
      );
    case 'beyond_followers':
      return (
        <>
          <span className="big">{f.best_ratio}×</span>
          {head}
          {sub}
          <p className="note">{f.note}</p>
        </>
      );
    case 'top_reel':
    case 'most_talked':
    case 'most_shared':
      return (
        <>
          <div style={{ border: '2px solid currentColor', borderRadius: 20, padding: '16px 18px' }}>
            <p className="sub" style={{ fontWeight: 600 }}>
              “{f.title}”
            </p>
          </div>
          {head}
          {sub}
        </>
      );
    case 'growth':
      return (
        <>
          {typeof f.delta === 'number' ? (
            <CountUp to={f.delta} reduced={reduced} format={(n) => `${n >= 0 ? '+' : ''}${fmtIn(n)}`} />
          ) : (
            <CountUp to={f.gap} reduced={reduced} />
          )}
          {head}
          {sub}
        </>
      );
    case 'audience_voice':
      return (
        <>
          {head}
          {f.top_comment ? (
            <div style={{ background: 'rgba(255,255,255,0.7)', color: '#242424', borderRadius: 20, padding: '14px 16px' }}>
              <p className="sub">“{f.top_comment}”</p>
              <p className="note" style={{ marginTop: 6 }}>
                {fmtIn(f.top_comment_likes)} likes{f.emoji ? ` · most-used emoji ${f.emoji}` : ''}
              </p>
            </div>
          ) : null}
          {sub}
        </>
      );
    case 'language_mix':
      return (
        <>
          {head}
          {(f.mix as { language: string; share: number }[]).map((m) => (
            <div key={m.language}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                <span>{m.language}</span>
                <span>{Math.round(m.share * 100)}%</span>
              </div>
              <div style={{ height: 10, borderRadius: 5, background: 'rgba(36,36,36,0.15)', marginTop: 6 }}>
                <div style={{ width: `${m.share * 100}%`, height: '100%', borderRadius: 5, background: accent }} />
              </div>
            </div>
          ))}
          {sub}
        </>
      );
    case 'creator_type':
      return (
        <>
          <p className="sub" style={{ opacity: 0.85 }}>
            You’re
          </p>
          <span className="big" style={{ fontSize: 44 }}>{recap.creator_level ?? 'A creator'}</span>
          <span className="big" style={{ fontSize: 40, color: COLOURS.lavender }}>
            {recap.archetype}
          </span>
          {recap.level_modifier ? (
            <span className="pill" style={{ alignSelf: 'flex-start', background: COLOURS.pink, color: '#242424' }}>
              {recap.level_modifier}
            </span>
          ) : null}
          <p className="sub">{f.level_line}</p>
          <p className="sub">{f.archetype_line}</p>
          {recap.archetype_runner_up ? <p className="note">With a dash of {recap.archetype_runner_up}.</p> : null}
        </>
      );
    case 'share_card':
      return <ShareCard recap={recap} />;
    case 'next_up':
      return (
        <>
          {head}
          {sub}
          <button className="btn block" style={{ height: 56, fontSize: 18, position: 'relative', zIndex: 3, pointerEvents: 'auto' }} onClick={onClose}>
            Let’s go
          </button>
        </>
      );
    default:
      return (
        <>
          {head}
          {sub}
        </>
      );
  }
}

/** The 1080×1920 card: the API draws the SVG, the browser makes the PNG (Share / Download). */
function ShareCard({ recap }: { recap: S['Recap'] }) {
  const [url, setUrl] = useState<string | null>(null);
  const [png, setPng] = useState<Blob | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    let objectUrl = '';
    apiText(`/recaps/${recap.id}/share-image`)
      .then(async (svg) => {
        objectUrl = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
        if (!alive) return;
        setUrl(objectUrl);
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          canvas.width = 1080;
          canvas.height = 1920;
          canvas.getContext('2d')?.drawImage(img, 0, 0, 1080, 1920);
          canvas.toBlob((b) => alive && setPng(b), 'image/png');
        };
        img.src = objectUrl;
      })
      .catch(() => setMsg('The share card couldn’t be drawn.'));
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [recap.id]);

  const name = `curo-recap-${recap.period_start}.png`;
  const download = () => {
    if (!png) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(png);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  const share = async () => {
    if (!png) return;
    const file = new File([png], name, { type: 'image/png' });
    const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
    if (nav.canShare?.({ files: [file] })) {
      try {
        await nav.share({ files: [file], title: 'My Creator Recap' });
      } catch {
        /* closed the share sheet */
      }
    } else {
      download();
      setMsg('Sharing images isn’t supported here, so it was downloaded instead.');
    }
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center', position: 'relative', zIndex: 3, pointerEvents: 'auto' }}>
      {url ? (
        <img src={url} alt={`Your recap card: ${recap.creator_level ?? ''} ${recap.archetype ?? ''}`} style={{ width: '62%', borderRadius: 18, boxShadow: '0 0 0 1px rgba(36,36,36,0.15)' }} />
      ) : (
        <div className="skeleton" style={{ width: '62%', aspectRatio: '9 / 16' }} />
      )}
      <div style={{ display: 'flex', gap: 10, width: '100%' }}>
        <button className="btn" style={{ flex: 1 }} onClick={share} disabled={!png}>
          Share
        </button>
        <button className="btn ghost" style={{ flex: 1 }} onClick={download} disabled={!png}>
          Download
        </button>
      </div>
      {msg ? <p className="note">{msg}</p> : null}
    </div>
  );
}

export function StoryPlayer({
  recap,
  start = 0,
  onClose,
  onSeen,
}: {
  recap: S['Recap'];
  start?: number;
  onClose: () => void;
  onSeen?: () => void;
}) {
  const slides = recap.slides ?? [];
  const reduced = useReducedMotion();
  const [i, setI] = useState(Math.min(Math.max(0, start), Math.max(0, slides.length - 1)));
  const [progress, setProgress] = useState(0);
  const [paused, setPaused] = useState(false);
  const [how, setHow] = useState(false);
  const [mounted, setMounted] = useState(false);
  const hold = useRef<{ t: number; x: number; y: number; timer: number; held: boolean } | null>(null);
  const seen = useRef(false);

  useEffect(() => setMounted(true), []);
  const slide = slides[i];
  const seconds = slide?.visual.seconds ?? 6;

  const next = useCallback(() => {
    setProgress(0);
    setI((k) => {
      if (k >= slides.length - 1) {
        if (!seen.current) {
          seen.current = true;
          onSeen?.();
        }
        return k;
      }
      return k + 1;
    });
  }, [slides.length, onSeen]);
  const back = useCallback(() => {
    setProgress(0);
    setI((k) => Math.max(0, k - 1));
  }, []);

  useEffect(() => {
    if (i === slides.length - 1 && !seen.current) {
      seen.current = true;
      onSeen?.();
    }
  }, [i, slides.length, onSeen]);

  // Auto-advance (never with reduced motion, never on the last slide, never while paused).
  useEffect(() => {
    if (reduced || paused || how || i >= slides.length - 1) return;
    const step = 100 / (seconds * 1000);
    let last = performance.now();
    const t = window.setInterval(() => {
      const now = performance.now();
      setProgress((p) => {
        const np = p + (now - last) * step;
        last = now;
        if (np >= 100) {
          window.setTimeout(next, 0);
          return 100;
        }
        return np;
      });
    }, 50);
    return () => window.clearInterval(t);
  }, [i, paused, how, reduced, seconds, slides.length, next]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (how) {
        if (e.key === 'Escape') setHow(false);
        return;
      }
      if (e.key === 'ArrowRight') next();
      else if (e.key === 'ArrowLeft') back();
      else if (e.key === ' ') {
        e.preventDefault();
        setPaused((p) => !p);
      } else if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [next, back, onClose, how]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  if (!mounted || !slide) return null;
  const bg = COLOURS[slide.visual.bg] ?? COLOURS.lavender;
  const fg = COLOURS[slide.visual.fg] ?? COLOURS.ink;
  const accent = COLOURS[slide.visual.accent] ?? COLOURS.blue;
  const f = slide.facts as Record<string, any>;

  const down = (e: React.PointerEvent) => {
    const timer = window.setTimeout(() => {
      if (hold.current) {
        hold.current.held = true;
        setPaused(true);
      }
    }, 220);
    hold.current = { t: Date.now(), x: e.clientX, y: e.clientY, timer, held: false };
  };
  const up = (e: React.PointerEvent) => {
    const h = hold.current;
    hold.current = null;
    if (!h) return;
    window.clearTimeout(h.timer);
    if (h.held) {
      setPaused(false);
      return;
    }
    if (e.clientY - h.y > 90 && Math.abs(e.clientX - h.x) < 80) return onClose(); // swipe down
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    if (e.clientX - rect.left < rect.width / 3) back();
    else next();
  };

  return createPortal(
    <div className="story" role="dialog" aria-modal="true" aria-label={`Creator Recap: ${recap.period_label}`}>
      <div className="story-col" style={{ background: bg, color: fg }}>
        <div className="story-bars" aria-hidden="true">
          {slides.map((_, k) => (
            <span key={k}>
              <i style={{ transform: `scaleX(${k < i ? 1 : k === i ? (reduced ? 1 : progress / 100) : 0})` }} />
            </span>
          ))}
        </div>
        <div className="story-top">
          <span>
            {recap.period_label} · {i + 1}/{slides.length}
            {paused ? ' · paused' : ''}
          </span>
          <span style={{ display: 'flex', gap: 4 }}>
            <button onClick={() => setPaused((p) => !p)} aria-label={paused ? 'Play' : 'Pause'}>
              {paused ? <Icon name="play" size={18} /> : <span style={{ fontWeight: 700, letterSpacing: 2 }}>II</span>}
            </button>
            <button onClick={onClose} aria-label="Close the recap">
              <Icon name="close" size={22} strokeWidth={2} />
            </button>
          </span>
        </div>
        {slide.visual.milestone && !reduced ? <Confetti key={`confetti-${i}`} /> : null}
        <div
          className="story-tap"
          onPointerDown={down}
          onPointerUp={up}
          onPointerCancel={() => (hold.current = null)}
          aria-hidden="true"
        />
        <div className="story-body" key={`body-${i}`} aria-live="polite" style={{ pointerEvents: 'none' }}>
          <Body slide={slide} recap={recap} reduced={reduced} accent={accent} onClose={onClose} />
        </div>
        {slide.slide_id !== 'share_card' && slide.slide_id !== 'next_up' ? (
          <button className="story-how" onClick={() => setHow(true)}>
            ⓘ How we got this
          </button>
        ) : null}
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', gap: 8, paddingBottom: 6, zIndex: 3 }}>
          <button className="sr-only" onClick={back}>
            Previous slide
          </button>
          <button className="sr-only" onClick={next}>
            Next slide
          </button>
        </div>
        {how ? (
          <div className="overlay" style={{ position: 'absolute', zIndex: 5 }} onClick={() => setHow(false)} role="dialog" aria-modal="true" aria-labelledby="how-title">
            <div className="panel" onClick={(e) => e.stopPropagation()} style={{ color: '#242424' }}>
              <div className="row between">
                <h2 id="how-title" style={{ margin: 0, fontSize: 20 }}>
                  How we got this
                </h2>
                <button className="circle sm" onClick={() => setHow(false)} aria-label="Close">
                  <Icon name="close" size={18} />
                </button>
              </div>
              <ul style={{ paddingLeft: 18, lineHeight: 1.5 }}>
                {(f.display as string[]).map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
              <p className="small">{f.how}</p>
              {f.note ? <p className="small muted">{f.note}</p> : null}
              {slide.slide_id === 'creator_type' && recap.archetype_evidence ? (
                <p className="small muted">
                  Type scores:{' '}
                  {Object.entries((recap.archetype_evidence as any).scores ?? {})
                    .sort((a: any, b: any) => b[1] - a[1])
                    .slice(0, 4)
                    .map(([k, v]: any) => `${k.replaceAll('_', ' ')} ${Math.round(v * 100)}%`)
                    .join(' · ')}
                </p>
              ) : null}
              <p className="small muted">Public data only: CURO never sees saves, reach, watch time or who your followers are.</p>
            </div>
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
