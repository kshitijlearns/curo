import { ScrollView } from 'react-native';

import { SimIntro } from './SimIntro';
import { SimLoading, SimResult } from './SimResult';
import { useSheetScroll } from '@/screens/shell/useSheetScroll';
import { useApp } from '@/state/app';

/** Simulator: upload → simulating → result (logic doc §13, MVP doc T9). */
export function SimulatorView() {
  const ref = useSheetScroll();
  const view = useApp((s) => s.sim.view);
  return (
    <ScrollView ref={ref} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      {view === 'intro' ? <SimIntro /> : null}
      {view === 'loading' ? <SimLoading /> : null}
      {view === 'result' ? <SimResult /> : null}
    </ScrollView>
  );
}
