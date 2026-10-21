'use client';
/**
 * The app shell (prototype): a lavender header, a white sheet with a 32px rounded top, and a
 * dock with the Composer (where a chat applies) above the springy Nav. Saved opens over the
 * current tab with the Nav still showing.
 */
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { BackHeader, BrandHeader, Loading, Nav, Toast } from '@/components/Chrome';
import { Composer } from '@/components/Composer';
import { UpgradeSheet } from '@/components/UpgradeSheet';
import { signedIn } from '@/lib/session';
import { useMe, useOpportunity, useSaveOpportunity } from '@/lib/hooks';
import { HomeView } from '@/screens/HomeView';
import { OpportunityView } from '@/screens/OpportunityView';
import { SavedView } from '@/screens/SavedView';
import { SimulatorView } from '@/screens/SimulatorView';
import { StudioView } from '@/screens/StudioView';
import { AppProvider, useApp } from '@/state/app';

export default function Page() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    signedIn().then((ok) => (ok ? setReady(true) : router.replace('/login')));
  }, [router]);
  if (!ready) {
    return (
      <div className="app">
        <div className="sheet" style={{ marginTop: 120 }}>
          <Loading />
        </div>
      </div>
    );
  }
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}

function Shell() {
  const router = useRouter();
  const s = useApp();
  const me = useMe();
  const opp = useOpportunity(s.tab === 'home' ? s.oppId : null);
  const save = useSaveOpportunity();

  useEffect(() => {
    if (me.data && !me.data.onboarded) router.replace('/onboarding');
  }, [me.data, router]);

  let header: React.ReactNode;
  if (s.saved) {
    header = (
      <BackHeader title="Saved" onBack={() => s.setSaved(false)} sub="Opportunity areas and Studio drafts you kept" />
    );
  } else if (s.tab === 'home' && s.oppId) {
    const saved = save.isPending ? !!save.variables?.save : !!opp.data?.saved;
    header = (
      <BackHeader
        title="Opportunity area"
        onBack={() => s.openOpp(null)}
        bookmark={{
          saved,
          onToggle: () =>
            opp.data &&
            save.mutate(
              { id: opp.data.id, save: !opp.data.saved },
              {
                onSuccess: (_d, v) =>
                  s.showToast(v.save ? 'Saved. Find it under Saved at the top of the app.' : 'Removed from saved.'),
              },
            ),
        }}
      />
    );
  } else {
    header = (
      <BrandHeader
        savedCount={me.data?.saved_count ?? 0}
        onSaved={() => s.setSaved(true)}
        initial={me.data?.account?.username ?? me.data?.email}
      />
    );
  }

  let view: React.ReactNode;
  if (s.saved) view = <SavedView />;
  else if (s.tab === 'home') view = s.oppId ? <OpportunityView id={s.oppId} /> : <HomeView />;
  else if (s.tab === 'studio') view = <StudioView />;
  else view = <SimulatorView />;

  const composer = s.saved || s.tab === 'home' ? null : s.composer;
  return (
    <div className="app">
      {header}
      <main className="sheet" style={{ paddingBottom: composer ? 230 : 140 }}>
        {view}
      </main>
      <div className="dock">
        <div className="dock-inner">
          {composer ? (
            <Composer
              placeholder={composer.placeholder}
              hint={composer.hint}
              busy={composer.busy}
              onSend={composer.onSend}
              onNotice={s.showToast}
            />
          ) : null}
          <Nav active={s.tab} onNav={s.nav} />
        </div>
      </div>
      {s.toast ? <Toast key={s.toast.id} text={s.toast.text} /> : null}
      {s.limit ? <UpgradeSheet limit={s.limit} onClose={s.clearLimit} /> : null}
    </div>
  );
}
