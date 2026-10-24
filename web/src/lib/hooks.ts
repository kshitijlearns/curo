'use client';
/** React Query hooks over the typed client. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, type S } from './api';

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: () => api<S['Me']>('/me') });

export const useOpportunities = () =>
  useQuery({ queryKey: ['opps'], queryFn: () => api<S['OpportunityCard'][]>('/opportunities') });

export const useOpportunity = (id: string | null) =>
  useQuery({
    queryKey: ['opp', id],
    queryFn: () => api<S['OpportunityDetail']>(`/opportunities/${id}`),
    enabled: !!id,
  });

export const useTrends = () =>
  useQuery({ queryKey: ['trends'], queryFn: () => api<S['TrendCard'][]>('/trends') });

export const useSaved = () =>
  useQuery({ queryKey: ['saved'], queryFn: () => api<S['SavedOut']>('/saved') });

export const useProject = (id: string | null) =>
  useQuery({
    queryKey: ['project', id],
    queryFn: () => api<S['Project']>(`/projects/${id}`),
    enabled: !!id,
    // A new project's first three ideas are written in the background: poll until they land.
    refetchInterval: (q) => (q.state.data && (q.state.data.rounds ?? []).length === 0 ? 1500 : false),
  });

export const useSimulation = (id: string | null) =>
  useQuery({
    queryKey: ['sim', id],
    queryFn: () => api<S['Simulation']>(`/simulations/${id}`),
    enabled: !!id,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'queued' || s === 'running' ? 1500 : false;
    },
  });

export const useBilling = () =>
  useQuery({ queryKey: ['billing'], queryFn: () => api<S['BillingOut']>('/billing') });

export const useMemory = () =>
  useQuery({ queryKey: ['memory'], queryFn: () => api<S['MemoryOut'][]>('/memory') });

export function useSaveOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, save }: { id: string; save: boolean }) =>
      api<S['OpportunityCard']>(`/opportunities/${id}/save`, { method: save ? 'POST' : 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['opps'] });
      qc.invalidateQueries({ queryKey: ['opp'] });
      qc.invalidateQueries({ queryKey: ['me'] });
      qc.invalidateQueries({ queryKey: ['saved'] });
    },
  });
}

// ---------------------------------------------------------------- v2.1

export const useLatestRecap = () =>
  useQuery({
    queryKey: ['recap', 'latest'],
    queryFn: () => api<S['Recap'] | null>('/recaps/latest'),
    refetchInterval: (q) => (q.state.data?.status === 'building' ? 2000 : false),
  });

export const useRecaps = () =>
  useQuery({ queryKey: ['recaps'], queryFn: () => api<S['RecapSummary'][]>('/recaps') });

export const useRecap = (id: string | null) =>
  useQuery({
    queryKey: ['recap', id],
    queryFn: () => api<S['Recap']>(`/recaps/${id}`),
    enabled: !!id,
  });

export const useFollowerIdeas = () =>
  useQuery({ queryKey: ['follower-ideas'], queryFn: () => api<S['FollowerIdeaOut'][]>('/follower-ideas') });

export const useOnboardingStatus = (enabled = true) =>
  useQuery({
    queryKey: ['onboarding'],
    queryFn: () => api<S['OnboardingStatus']>('/onboarding/status'),
    enabled,
    refetchInterval: (q) =>
      q.state.data?.step === 'recap_ready' || q.state.data?.status === 'failed' ? false : 1500,
  });
