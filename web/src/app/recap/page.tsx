'use client';
/**
 * Plays a Creator Recap full screen. After the first recap ("your story so far") an anonymous
 * creator is asked to save their account (v2.1 §2 step 5); otherwise closing goes to Home.
 */
import { useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect } from 'react';

import { ErrorNote, Loading } from '@/components/Chrome';
import { StoryPlayer } from '@/components/StoryPlayer';
import { api } from '@/lib/api';
import { useMe, useRecap } from '@/lib/hooks';
import { signedIn } from '@/lib/session';

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <div className="sheet" style={{ marginTop: 120 }}>
        {children}
      </div>
    </div>
  );
}

function RecapPage() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const id = params.get('id');
  const first = params.get('first') === '1';
  const start = Number(params.get('slide') ?? 0) || 0;
  const q = useRecap(id);
  const me = useMe();

  useEffect(() => {
    signedIn().then((ok) => !ok && router.replace('/start'));
  }, [router]);

  const seen = useCallback(() => {
    if (!id) return;
    api(`/recaps/${id}/viewed`, { body: {} })
      .then(() => qc.invalidateQueries({ queryKey: ['recap'] }))
      .catch(() => undefined);
  }, [id, qc]);

  const close = () => {
    seen();
    if (first && me.data?.is_anonymous) router.replace('/save');
    else router.replace('/');
  };

  if (!id) {
    return (
      <Frame>
        <ErrorNote error={new Error('No recap chosen.')} />
      </Frame>
    );
  }
  if (q.isLoading) {
    return (
      <Frame>
        <Loading text="Opening your recap…" />
      </Frame>
    );
  }
  if (q.error || !q.data) {
    return (
      <Frame>
        <ErrorNote error={q.error} onRetry={() => q.refetch()} />
      </Frame>
    );
  }
  return <StoryPlayer recap={q.data} start={start} onClose={close} onSeen={seen} />;
}

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <RecapPage />
    </Suspense>
  );
}
