import { useEffect, useRef } from 'react';
import type { ScrollView } from 'react-native';

import { useApp } from '@/state/app';

/**
 * Ref for a view's main ScrollView that follows the store's scroll requests
 * (the prototype's top() / bottom()). Requests made before the view mounted are ignored.
 */
export function useSheetScroll() {
  const ref = useRef<ScrollView>(null);
  const scroll = useApp((s) => s.scroll);
  const seen = useRef(scroll.n);

  useEffect(() => {
    if (scroll.n === seen.current) return;
    seen.current = scroll.n;
    if (scroll.kind === 'top') ref.current?.scrollTo({ y: 0, animated: false });
    else ref.current?.scrollToEnd({ animated: true });
  }, [scroll]);

  return ref;
}
