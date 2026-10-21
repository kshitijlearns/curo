'use client';
/**
 * What the shell shows: the tab, Saved over it, the opportunity open on Home, the Studio
 * project, the simulation, a toast, and the out-of-credits screen when the API says 402.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import type { Limit } from '@/lib/api';

export type Tab = 'home' | 'studio' | 'sim';

type Composer = {
  placeholder: string;
  hint?: string;
  busy?: boolean;
  onSend: (text: string) => void;
} | null;

type AppState = {
  tab: Tab;
  nav: (t: Tab) => void;
  saved: boolean;
  setSaved: (v: boolean) => void;
  oppId: string | null;
  openOpp: (id: string | null) => void;
  projectId: string | null;
  openProject: (id: string | null) => void;
  simId: string | null;
  openSim: (id: string | null) => void;
  toast: { id: number; text: string } | null;
  showToast: (text: string) => void;
  limit: Limit | null;
  clearLimit: () => void;
  composer: Composer;
  setComposer: (c: Composer) => void;
};

const Ctx = createContext<AppState | null>(null);

function readUrl() {
  if (typeof window === 'undefined') return {} as Record<string, string>;
  return Object.fromEntries(new URLSearchParams(window.location.search));
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [tab, setTab] = useState<Tab>('home');
  const [saved, setSaved] = useState(false);
  const [oppId, setOppId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [simId, setSimId] = useState<string | null>(null);
  const [toast, setToast] = useState<AppState['toast']>(null);
  const [limit, setLimit] = useState<Limit | null>(null);
  const [composer, setComposer] = useState<Composer>(null);

  // Deep links: ?tab=studio&project=… / ?tab=sim&sim=… (the URL follows what's open).
  useEffect(() => {
    const q = readUrl();
    if (q.tab === 'studio' || q.tab === 'sim' || q.tab === 'home') setTab(q.tab);
    if (q.project) setProjectId(q.project);
    if (q.sim) setSimId(q.sim);
    if (q.opp) setOppId(q.opp);
  }, []);
  useEffect(() => {
    const q = new URLSearchParams();
    if (tab !== 'home') q.set('tab', tab);
    if (tab === 'home' && oppId) q.set('opp', oppId);
    if (tab === 'studio' && projectId) q.set('project', projectId);
    if (tab === 'sim' && simId) q.set('sim', simId);
    const url = q.toString() ? `/?${q}` : '/';
    if (url !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(null, '', url);
    }
  }, [tab, oppId, projectId, simId]);

  useEffect(() => {
    const on = (e: Event) => setLimit((e as CustomEvent<Limit>).detail);
    window.addEventListener('curo:limit', on);
    return () => window.removeEventListener('curo:limit', on);
  }, []);

  const showToast = useCallback((text: string) => {
    const id = Date.now();
    setToast({ id, text });
    window.setTimeout(() => setToast((t) => (t?.id === id ? null : t)), 3600);
  }, []);

  const value = useMemo<AppState>(
    () => ({
      tab,
      nav: (t) => {
        setSaved(false);
        if (t === tab && t === 'home') setOppId(null);
        setTab(t);
        window.scrollTo({ top: 0 });
      },
      saved,
      setSaved,
      oppId,
      openOpp: (id) => {
        setOppId(id);
        window.scrollTo({ top: 0 });
      },
      projectId,
      openProject: (id) => {
        setSaved(false);
        setProjectId(id);
        setTab('studio');
        window.scrollTo({ top: 0 });
      },
      simId,
      openSim: (id) => {
        setSimId(id);
        setTab('sim');
        window.scrollTo({ top: 0 });
      },
      toast,
      showToast,
      limit,
      clearLimit: () => setLimit(null),
      composer,
      setComposer,
    }),
    [tab, saved, oppId, projectId, simId, toast, showToast, limit, composer],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppProvider');
  return v;
}
