import Svg, { Circle, Path, Rect } from 'react-native-svg';

import { colors } from '@/theme';

/** Every icon in the prototype, with its exact paths (24 × 24 viewBox). */
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
  | 'arrowDown'
  | 'sparkle'
  | 'check'
  | 'refresh'
  | 'upload'
  | 'simulate'
  | 'clock'
  | 'home'
  | 'studio'
  | 'simulator'
  | 'mic'
  | 'play';

type Props = {
  name: IconName;
  size?: number;
  color?: string;
  strokeWidth?: number;
  /** Fill the shape (bookmark when saved). */
  filled?: boolean;
};

const ROUND = { strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

export function Icon({ name, size = 20, color = colors.ink, strokeWidth = 1.7, filled }: Props) {
  const stroke = { stroke: color, strokeWidth, fill: 'none' };
  const fillOnly = { fill: color };
  let body: React.ReactNode;
  switch (name) {
    case 'views':
      body = (
        <>
          <Path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" {...stroke} {...ROUND} />
          <Circle cx={12} cy={12} r={3} {...stroke} />
        </>
      );
      break;
    case 'likes':
      body = (
        <Path
          d="M12 20s-7.5-4.6-9.2-9.3C1.7 7.4 3.8 4.5 7 4.5c2 0 3.3 1.1 5 3 1.7-1.9 3-3 5-3 3.2 0 5.3 2.9 4.2 6.2C19.5 15.4 12 20 12 20z"
          {...stroke}
          strokeLinejoin="round"
        />
      );
      break;
    case 'shares':
      body = (
        <Path
          d="M21.5 2.5L10 14M21.5 2.5l-7 19-4.5-7.5L2.5 9.5z"
          {...stroke}
          strokeLinejoin="round"
        />
      );
      break;
    case 'comments':
      body = (
        <Path
          d="M20.5 11.5a8.5 8.5 0 0 1-12.4 7.6L3 20.5l1.4-4.7A8.5 8.5 0 1 1 20.5 11.5z"
          {...stroke}
          strokeLinejoin="round"
        />
      );
      break;
    case 'bookmark':
      body = (
        <Path
          d="M6 3.5h12v17l-6-4.5-6 4.5z"
          {...stroke}
          fill={filled ? color : 'none'}
          strokeLinejoin="round"
        />
      );
      break;
    case 'back':
      body = <Path d="M15 6l-6 6 6 6" {...stroke} {...ROUND} />;
      break;
    case 'chevronRight':
      body = <Path d="M9 6l6 6-6 6" {...stroke} {...ROUND} />;
      break;
    case 'chevronDown':
      body = <Path d="M6 9l6 6 6-6" {...stroke} {...ROUND} />;
      break;
    case 'arrowRight':
      body = <Path d="M5 12h14M13 6l6 6-6 6" {...stroke} {...ROUND} />;
      break;
    case 'arrowUpRight':
      body = <Path d="M7 17L17 7M8 7h9v9" {...stroke} strokeLinecap="round" />;
      break;
    case 'arrowDown':
      body = <Path d="M12 5v14M6 13l6 6 6-6" {...stroke} strokeLinecap="round" />;
      break;
    case 'sparkle':
      body = (
        <Path
          d="M12 2c.8 5.6 3.4 8.2 9 9-5.6.8-8.2 3.4-9 9-.8-5.6-3.4-8.2-9-9 5.6-.8 8.2-3.4 9-9z"
          {...fillOnly}
        />
      );
      break;
    case 'check':
      body = <Path d="M5 12.5l4.5 4.5L19 7.5" {...stroke} {...ROUND} />;
      break;
    case 'refresh':
      body = <Path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5" {...stroke} {...ROUND} />;
      break;
    case 'upload':
      body = <Path d="M12 16V4M6 10l6-6 6 6M4 20h16" {...stroke} {...ROUND} />;
      break;
    case 'simulate':
      body = <Path d="M3 12h4l3-7 4 14 3-7h4" {...stroke} {...ROUND} />;
      break;
    case 'clock':
      body = (
        <>
          <Circle cx={12} cy={12} r={9} {...stroke} />
          <Path d="M12 7v5l3 2" {...stroke} strokeLinecap="round" />
        </>
      );
      break;
    case 'home':
      body = (
        <Path
          d="M3.5 10.2L12 3.5l8.5 6.7V20a1 1 0 0 1-1 1H15v-6h-6v6H4.5a1 1 0 0 1-1-1z"
          {...stroke}
          strokeLinejoin="round"
        />
      );
      break;
    case 'studio':
      body = (
        <>
          <Path
            d="M12 2.5a7 7 0 0 0-4 12.7V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-1.8A7 7 0 0 0 12 2.5z"
            {...stroke}
            {...ROUND}
          />
          <Path d="M9.5 20.5h5" {...stroke} {...ROUND} />
        </>
      );
      break;
    case 'simulator':
      body = <Path d="M2.5 12h4l2.5-6 4.5 12 2.5-6h5.5" {...stroke} {...ROUND} />;
      break;
    case 'mic':
      body = (
        <>
          <Rect x={9} y={3} width={6} height={11} rx={3} {...stroke} />
          <Path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M9 21h6" {...stroke} {...ROUND} />
        </>
      );
      break;
    case 'play':
      body = <Path d="M7 4.5v15l12-7.5z" {...fillOnly} />;
      break;
  }
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      {body}
    </Svg>
  );
}
