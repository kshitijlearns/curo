import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  BackHandler,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { composerFor } from './composer';
import { useMe, useReels, useSaveOpportunity } from '@/api/hooks';
import { Composer } from '@/components/Composer';
import { BackHeader, BrandHeader } from '@/components/Header';
import { Nav } from '@/components/Nav';
import { Toast } from '@/components/Toast';
import { HomeView } from '@/screens/home/HomeView';
import { InsightsView } from '@/screens/home/InsightsView';
import { OpportunityPager, useOpportunityPages } from '@/screens/home/OpportunityPager';
import { SavedView } from '@/screens/SavedView';
import { SimulatorView } from '@/screens/sim/SimulatorView';
import { StudioView } from '@/screens/studio/StudioView';
import { useApp } from '@/state/app';
import { colors } from '@/theme';

/**
 * The app shell from the prototype: a fixed lavender header, a white sheet with a 32px
 * rounded top that scrolls under it, and a dock with the Composer (when a chat applies)
 * above the springy Nav. Saved opens over the current tab with the Nav still showing.
 */
export function Shell() {
  const insets = useSafeAreaInsets();
  const s = useApp();
  const me = useMe();
  const reels = useReels(10).data ?? [];
  const keyboard = useKeyboardVisible();
  useAndroidBack();

  const composer = composerFor(s);
  const homeRoot = !s.overlay && s.tab === 'home' && s.homeView === 'home';
  const savedCount = me.data?.saved_count ?? 0;
  const { pages, index: oppIdx } = useOpportunityPages();
  const saveOpp = useSaveOpportunity();
  const currentOpp = pages[oppIdx];
  const toggleSave = () => {
    if (!currentOpp) return;
    const save = !currentOpp.saved;
    saveOpp.mutate(
      { id: currentOpp.id, save },
      {
        onSuccess: () =>
          s.showToast(
            save
              ? 'Saved. Find it under Saved at the top of Home, Studio or Simulator.'
              : 'Removed from saved.',
          ),
      },
    );
  };

  let header: React.ReactNode;
  if (s.overlay === 'saved') {
    header = (
      <BackHeader
        topInset={insets.top}
        title="Saved"
        onBack={s.closeSaved}
        sub="Opportunity areas and Studio drafts you kept"
      />
    );
  } else if (s.tab === 'home' && s.homeView === 'insights') {
    header = (
      <BackHeader
        topInset={insets.top}
        title="Insights"
        onBack={s.goHomeRoot}
        sub={reels[Math.min(s.reelIdx, reels.length - 1)]?.title}
      />
    );
  } else if (s.tab === 'home' && s.homeView === 'opportunity') {
    header = (
      <BackHeader
        topInset={insets.top}
        title="Opportunity areas"
        onBack={s.goHomeRoot}
        bookmark={{
          saved: (saveOpp.isPending ? saveOpp.variables?.save : currentOpp?.saved) ?? false,
          onToggle: toggleSave,
        }}
        dots={{ count: pages.length, index: oppIdx, onGo: (i) => s.setOpp(pages[i].id) }}
      />
    );
  } else {
    header = (
      <BrandHeader
        topInset={insets.top}
        savedCount={savedCount}
        onSaved={s.openSaved}
        initial={me.data?.creator?.ig_username ?? me.data?.email ?? undefined}
        onProfile={() => router.push('/settings')}
      />
    );
  }

  let view: React.ReactNode;
  if (s.overlay === 'saved') view = <SavedView />;
  else if (s.tab === 'home') {
    view =
      s.homeView === 'insights' ? (
        <InsightsView />
      ) : s.homeView === 'opportunity' ? (
        <OpportunityPager />
      ) : (
        <HomeView />
      );
  } else if (s.tab === 'studio') view = <StudioView />;
  else view = <SimulatorView />;

  const bottomInset = keyboard ? 0 : insets.bottom;
  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      {header}
      <View style={styles.sheet}>{view}</View>
      <View
        style={[
          styles.dock,
          {
            backgroundColor: homeRoot ? colors.lavender : colors.white,
            paddingTop: homeRoot ? 0 : 10,
          },
        ]}
      >
        {composer ? (
          <View style={{ paddingHorizontal: 16, paddingBottom: keyboard ? 10 : 18 }}>
            <Composer
              key={composer.key}
              placeholder={composer.placeholder}
              hint={keyboard ? undefined : composer.hint}
              busy={(s.tab === 'studio' && !!s.studio.busy) || !!s.asking}
              onSend={s.composerSend}
              onNotice={s.showToast}
            />
          </View>
        ) : null}
        {keyboard && composer ? null : (
          <Nav active={s.tab} onNav={s.nav} bottomInset={bottomInset} />
        )}
      </View>
      {s.toast ? (
        <Toast
          key={s.toast.id}
          message={s.toast.text}
          bottom={(composer ? 190 : 104) + bottomInset}
        />
      ) : null}
    </KeyboardAvoidingView>
  );
}

function useKeyboardVisible() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const show = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      () => setVisible(true),
    );
    const hide = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide',
      () => setVisible(false),
    );
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);
  return visible;
}

/** Android back: close Saved, leave Insights/Opportunity, step back in Studio, then Home. */
function useAndroidBack() {
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      const s = useApp.getState();
      if (s.overlay) {
        s.closeSaved();
        return true;
      }
      if (s.tab === 'home' && s.homeView !== 'home') {
        s.goHomeRoot();
        return true;
      }
      if (s.tab === 'studio') {
        const order = ['ideas', 'idea', 'script', 'storyboard', 'caption', 'final'] as const;
        const stepOf = {
          ideas: 0,
          idea: 1,
          script: 1,
          storyboard: 2,
          caption: 3,
          final: 4,
        } as const;
        if (order.indexOf(s.studio.stage) > 0) {
          s.goStep(stepOf[s.studio.stage] - 1);
          return true;
        }
      }
      if (s.tab === 'sim' && s.sim.view === 'result') {
        s.backToIntro();
        return true;
      }
      if (s.tab !== 'home') {
        s.nav('home');
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, []);
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.lavender },
  sheet: {
    flex: 1,
    minHeight: 0,
    marginTop: -32,
    zIndex: 1,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    backgroundColor: colors.white,
    overflow: 'hidden',
  },
  dock: { zIndex: 2 },
});
