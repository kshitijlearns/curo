'use client';
/**
 * A Home section (v2.1 §5): a title with "See all", then a horizontal carousel — cards snap
 * into place, the next one peeks, page dots underneath; arrow keys and trackpads scroll it.
 * "See all" shows the same cards as a full list.
 */
import { Children, useEffect, useRef, useState } from 'react';

export function Section({
  title,
  children,
  label,
  onRetry,
  error,
  intro,
  footer,
}: {
  title: string;
  children: React.ReactNode;
  label?: string;
  onRetry?: () => void;
  error?: unknown;
  intro?: React.ReactNode; // a line between the title and the cards
  footer?: React.ReactNode;
}) {
  const [all, setAll] = useState(false);
  const count = Children.count(children);
  return (
    <section aria-label={label ?? title}>
      <div className="section-head">
        <h2>{title}</h2>
        {count > 1 && !error ? (
          <button onClick={() => setAll((v) => !v)} aria-expanded={all}>
            {all ? 'Show less' : 'See all'}
          </button>
        ) : null}
      </div>
      {intro}
      {error ? (
        <div className="card pink" role="alert">
          <p>This section didn’t load.</p>
          {onRetry ? (
            <button className="btn small ghost" style={{ marginTop: 10 }} onClick={onRetry}>
              Try again
            </button>
          ) : null}
        </div>
      ) : all ? (
        <div className="stack">{children}</div>
      ) : (
        <Carousel label={label ?? title}>{children}</Carousel>
      )}
      {footer}
    </section>
  );
}

export function Carousel({ children, label }: { children: React.ReactNode; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(0);
  const items = Children.toArray(children);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const on = () => {
      const kids = Array.from(el.children) as HTMLElement[];
      const x = el.scrollLeft;
      let best = 0;
      kids.forEach((k, i) => {
        if (Math.abs(k.offsetLeft - el.offsetLeft - 16 - x) < Math.abs(kids[best].offsetLeft - el.offsetLeft - 16 - x)) best = i;
      });
      setPage(best);
    };
    el.addEventListener('scroll', on, { passive: true });
    return () => el.removeEventListener('scroll', on);
  }, []);

  const go = (i: number) => {
    const el = ref.current;
    const kid = el?.children[i] as HTMLElement | undefined;
    if (el && kid) el.scrollTo({ left: kid.offsetLeft - el.offsetLeft - 16, behavior: 'smooth' });
  };

  return (
    <>
      <div
        ref={ref}
        className="carousel"
        role="region"
        aria-roledescription="carousel"
        aria-label={label}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') {
            e.preventDefault();
            go(Math.min(items.length - 1, page + 1));
          } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            go(Math.max(0, page - 1));
          }
        }}
      >
        {items}
      </div>
      {items.length > 1 ? (
        <div className="dots">
          {items.map((_, i) => (
            <button key={i} aria-label={`${label}: card ${i + 1} of ${items.length}`} aria-current={i === page} onClick={() => go(i)} />
          ))}
        </div>
      ) : null}
    </>
  );
}
