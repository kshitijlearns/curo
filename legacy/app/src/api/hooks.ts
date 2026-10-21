/** Data hooks over the typed API client (React Query handles caching and refetching). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { deleteMemory, listMemory } from './chat';
import { api, unwrap } from './client';
import { waitForJob } from './jobs';
import { toReelVM } from './reels';
import { getSimulation, listSamples, samplesKey, simulationKey } from './simulator';
import { getProject, projectKey } from './studio';
import { useSession } from '@/state/session';

export const keys = {
  me: ['me'] as const,
  onboarding: ['onboarding'] as const,
  reels: (limit: number) => ['reels', limit] as const,
  insights: (reelId: string) => ['reels', 'insights', reelId] as const,
  opportunities: ['opportunities'] as const,
  opportunity: (id: string) => ['opportunities', id] as const,
  saved: ['saved'] as const,
  peers: ['peers'] as const,
  memory: ['memory'] as const,
  matches: ['matches'] as const,
};

export function useMe() {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => unwrap(await api.GET('/v1/me')),
    enabled: signedIn,
  });
}

/** Onboarding progress; polls every second while a job is running (or `poll` is set). */
export function useOnboardingStatus(poll: boolean) {
  return useQuery({
    queryKey: keys.onboarding,
    queryFn: async () => unwrap(await api.GET('/v1/onboarding/status')),
    refetchInterval: (q) => (poll || q.state.data?.status === 'running' ? 1000 : false),
  });
}

export function useReels(limit = 10) {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.reels(limit),
    queryFn: async () =>
      unwrap(await api.GET('/v1/reels', { params: { query: { limit } } })).map(toReelVM),
    enabled: signedIn,
  });
}

/** Insights for one reel: phase, audience cards and top comment (logic doc §7). */
export function useInsights(reelId: string | undefined) {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.insights(reelId ?? ''),
    queryFn: async () =>
      unwrap(
        await api.GET('/v1/reels/{reel_id}/insights', { params: { path: { reel_id: reelId! } } }),
      ),
    enabled: signedIn && !!reelId,
    staleTime: 60_000,
  });
}

/** The top 5 opportunity areas (logic doc §8). */
export function useOpportunities() {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.opportunities,
    queryFn: async () => unwrap(await api.GET('/v1/opportunities')),
    enabled: signedIn,
    staleTime: 60_000,
  });
}

export function useOpportunity(id: string | undefined) {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.opportunity(id ?? ''),
    queryFn: async () =>
      unwrap(
        await api.GET('/v1/opportunities/{opportunity_id}', {
          params: { path: { opportunity_id: id! } },
        }),
      ),
    enabled: signedIn && !!id,
    staleTime: 60_000,
  });
}

function useAfterOpportunityChange() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: keys.opportunities });
    qc.invalidateQueries({ queryKey: keys.saved });
    qc.invalidateQueries({ queryKey: keys.me });
  };
}

/** Bookmark or un-bookmark an opportunity. */
export function useSaveOpportunity() {
  const refresh = useAfterOpportunityChange();
  return useMutation({
    mutationFn: async ({ id, save }: { id: string; save: boolean }) => {
      const params = { params: { path: { opportunity_id: id } } };
      return unwrap(
        save
          ? await api.POST('/v1/opportunities/{opportunity_id}/save', params)
          : await api.DELETE('/v1/opportunities/{opportunity_id}/save', params),
      );
    },
    onSettled: refresh,
  });
}

/** Hide an opportunity ("Not for me"); the signal is recorded. */
export function useDismissOpportunity() {
  const refresh = useAfterOpportunityChange();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.POST('/v1/opportunities/{opportunity_id}/dismiss', {
        params: { path: { opportunity_id: id } },
      });
      if (res.error) unwrap(res);
      return id;
    },
    onSettled: refresh,
  });
}

/** A Studio project: ideas, script, storyboard and captions under one id. */
export function useProject(projectId: string | null) {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: projectKey(projectId ?? ''),
    queryFn: () => getProject(projectId!),
    enabled: signedIn && !!projectId,
    staleTime: 5 * 60_000,
  });
}

/** A simulation: its status, then its full result (logic doc §13). */
export function useSimulation(simulationId: string | null) {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: simulationKey(simulationId ?? ''),
    queryFn: () => getSimulation(simulationId!),
    enabled: signedIn && !!simulationId,
    staleTime: 5 * 60_000,
  });
}

/** Sample recordings to try the Simulator with (the demo's takes; none with a real provider). */
export function useSamples() {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: samplesKey,
    queryFn: listSamples,
    enabled: signedIn,
    staleTime: Infinity,
  });
}

/** What Curo remembers about the creator (stated and learned), shown in Settings. */
export function useMemory() {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({ queryKey: keys.memory, queryFn: listMemory, enabled: signedIn });
}

export function useDeleteMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteMemory,
    onSettled: () => qc.invalidateQueries({ queryKey: keys.memory }),
  });
}

export function useSaved() {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.saved,
    queryFn: async () => unwrap(await api.GET('/v1/saved')),
    enabled: signedIn,
  });
}

/** Creators you track, and suggestions (polls while suggestions are being found). */
export function usePeers(poll = false) {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.peers,
    queryFn: async () => unwrap(await api.GET('/v1/peers/suggestions')),
    enabled: signedIn,
    refetchInterval: (q) => (poll && (q.state.data?.finding ?? true) ? 1500 : false),
  });
}

export function useTrackPeers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { account_ids?: string[]; username?: string }) => {
      const res = await api.POST('/v1/peers', { body });
      const out = unwrap(res) as { job_id?: string };
      if (out.job_id) {
        const job = await waitForJob(out.job_id, { timeoutMs: 60_000 });
        if (job.status === 'failed') throw new Error(job.error ?? 'Couldn’t add that account.');
      }
      return out;
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.peers }),
  });
}

export function useRemovePeer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (accountId: string) =>
      unwrap(
        await api.DELETE('/v1/peers/{account_id}', { params: { path: { account_id: accountId } } }),
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.peers }),
  });
}

export function useRequestCode() {
  return useMutation({
    mutationFn: async (email: string) =>
      unwrap(await api.POST('/v1/auth/otp', { body: { email } })),
  });
}

export function useVerifyCode() {
  const signIn = useSession((s) => s.signIn);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ email, code }: { email: string; code: string }) =>
      unwrap(await api.POST('/v1/auth/verify', { body: { email, code } })),
    onSuccess: async (s) => {
      qc.clear();
      await signIn({ token: s.access_token, email: s.email ?? null });
    },
  });
}

export function useStartOnboarding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (username: string) =>
      unwrap(await api.POST('/v1/onboarding/username', { body: { username } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.onboarding }),
  });
}

/** Pull to refresh: asks for a new snapshot (only if the data is 3 h old) and waits for it. */
export function useRefreshReels() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const out = unwrap(await api.POST('/v1/reels/refresh'));
      if (out.status === 'queued' && out.job_id)
        await waitForJob(out.job_id, { timeoutMs: 60_000 });
      return out;
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['reels'] });
      qc.invalidateQueries({ queryKey: keys.me });
    },
  });
}

/**
 * Posted reels that look like one the creator simulated or drafted (logic doc §15: "asks the
 * creator to confirm the match"). Confirmed, Home's arrow compares the reel with its
 * simulation and the accuracy record counts it.
 */
export function useMatches() {
  const signedIn = useSession((s) => !!s.session);
  return useQuery({
    queryKey: keys.matches,
    queryFn: async () => unwrap(await api.GET('/v1/matches')),
    enabled: signedIn,
    staleTime: 60_000,
  });
}

export function useDecideMatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, confirm }: { id: string; confirm: boolean }) => {
      const params = { params: { path: { match_id: id } } };
      return unwrap(
        confirm
          ? await api.POST('/v1/matches/{match_id}/confirm', params)
          : await api.POST('/v1/matches/{match_id}/reject', params),
      );
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.matches });
      qc.invalidateQueries({ queryKey: ['reels'] });
      qc.invalidateQueries({ queryKey: keys.saved });
    },
  });
}

/**
 * Delete the account and everything Curo holds about it (MVP doc §7, logic doc §17). The
 * server carries it out as a job; the app signs out straight away, since the session ends
 * with the account.
 */
export function useDeleteAccount() {
  const qc = useQueryClient();
  const signOut = useSession((s) => s.signOut);
  return useMutation({
    mutationFn: async () => unwrap(await api.DELETE('/v1/me')),
    onSuccess: async () => {
      qc.clear();
      await signOut();
    },
  });
}
