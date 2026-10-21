/** A score ring (0–100 or 0–10): a blue arc on a grey track, the number in the middle. */
export function ScoreRing({
  value,
  max = 100,
  size = 120,
  label,
  sub,
}: {
  value: number | null | undefined;
  max?: number;
  size?: number;
  label?: string;
  sub?: string;
}) {
  const r = (size - 14) / 2;
  const c = 2 * Math.PI * r;
  const known = value !== null && value !== undefined;
  const share = known ? Math.max(0, Math.min(1, (value as number) / max)) : 0;
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} role="img" aria-label={`${label ?? 'Score'}: ${known ? value : 'unknown'}${known ? ` of ${max}` : ''}`}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--gray)" strokeWidth={10} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="var(--blue)"
          strokeWidth={10}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - share)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 900ms var(--settle)' }}
        />
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span className="score" style={{ fontSize: size * 0.3 }}>
          {known ? value : '—'}
        </span>
        {sub ? <span className="small muted">{sub}</span> : null}
      </div>
    </div>
  );
}
