/** Every icon from the prototype, with its exact paths (24 × 24 viewBox). */
export type IconName =
  | 'views'
  | 'likes'
  | 'shares'
  | 'comments'
  | 'bookmark'
  | 'back'
  | 'chevronRight'
  | 'chevronDown'
  | 'arrowRight'
  | 'arrowUpRight'
  | 'sparkle'
  | 'check'
  | 'refresh'
  | 'upload'
  | 'clock'
  | 'home'
  | 'studio'
  | 'simulator'
  | 'mic'
  | 'play'
  | 'close'
  | 'send';

export function Icon({
  name,
  size = 20,
  color = 'currentColor',
  strokeWidth = 1.7,
  filled,
}: {
  name: IconName;
  size?: number;
  color?: string;
  strokeWidth?: number;
  filled?: boolean;
}) {
  const s = { stroke: color, strokeWidth, fill: 'none', strokeLinecap: 'round', strokeLinejoin: 'round' } as const;
  let body: React.ReactNode;
  switch (name) {
    case 'views':
      body = (
        <>
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" {...s} />
          <circle cx={12} cy={12} r={3} {...s} />
        </>
      );
      break;
    case 'likes':
      body = (
        <path
          d="M12 20s-7.5-4.6-9.2-9.3C1.7 7.4 3.8 4.5 7 4.5c2 0 3.3 1.1 5 3 1.7-1.9 3-3 5-3 3.2 0 5.3 2.9 4.2 6.2C19.5 15.4 12 20 12 20z"
          {...s}
        />
      );
      break;
    case 'shares':
      body = <path d="M21.5 2.5L10 14M21.5 2.5l-7 19-4.5-7.5L2.5 9.5z" {...s} />;
      break;
    case 'comments':
      body = (
        <path d="M20.5 11.5a8.5 8.5 0 0 1-12.4 7.6L3 20.5l1.4-4.7A8.5 8.5 0 1 1 20.5 11.5z" {...s} />
      );
      break;
    case 'bookmark':
      body = <path d="M6 3.5h12v17l-6-4.5-6 4.5z" {...s} fill={filled ? color : 'none'} />;
      break;
    case 'back':
      body = <path d="M15 6l-6 6 6 6" {...s} />;
      break;
    case 'chevronRight':
      body = <path d="M9 6l6 6-6 6" {...s} />;
      break;
    case 'chevronDown':
      body = <path d="M6 9l6 6 6-6" {...s} />;
      break;
    case 'arrowRight':
      body = <path d="M5 12h14M13 6l6 6-6 6" {...s} />;
      break;
    case 'arrowUpRight':
      body = <path d="M7 17L17 7M8 7h9v9" {...s} />;
      break;
    case 'sparkle':
      body = (
        <path
          d="M12 2c.8 5.6 3.4 8.2 9 9-5.6.8-8.2 3.4-9 9-.8-5.6-3.4-8.2-9-9 5.6-.8 8.2-3.4 9-9z"
          fill={color}
        />
      );
      break;
    case 'check':
      body = <path d="M5 12.5l4.5 4.5L19 7.5" {...s} />;
      break;
    case 'refresh':
      body = <path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5" {...s} />;
      break;
    case 'upload':
      body = <path d="M12 16V4M6 10l6-6 6 6M4 20h16" {...s} />;
      break;
    case 'clock':
      body = (
        <>
          <circle cx={12} cy={12} r={9} {...s} />
          <path d="M12 7v5l3 2" {...s} />
        </>
      );
      break;
    case 'home':
      body = (
        <path d="M3.5 10.2L12 3.5l8.5 6.7V20a1 1 0 0 1-1 1H15v-6h-6v6H4.5a1 1 0 0 1-1-1z" {...s} />
      );
      break;
    case 'studio':
      body = (
        <>
          <path
            d="M12 2.5a7 7 0 0 0-4 12.7V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-1.8A7 7 0 0 0 12 2.5z"
            {...s}
          />
          <path d="M9.5 20.5h5" {...s} />
        </>
      );
      break;
    case 'simulator':
      body = <path d="M2.5 12h4l2.5-6 4.5 12 2.5-6h5.5" {...s} />;
      break;
    case 'mic':
      body = (
        <>
          <rect x={9} y={3} width={6} height={11} rx={3} {...s} />
          <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" {...s} />
        </>
      );
      break;
    case 'play':
      body = <path d="M7 4.5v15l12-7.5z" fill={color} />;
      break;
    case 'close':
      body = <path d="M6 6l12 12M18 6L6 18" {...s} />;
      break;
    case 'send':
      body = <path d="M12 19V5M6 11l6-6 6 6" {...s} />;
      break;
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {body}
    </svg>
  );
}
