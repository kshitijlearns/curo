/**
 * JobWatcher: follow a slow job (onboarding, refresh, simulations) until it finishes.
 *
 * Locally this polls GET /v1/jobs/{id}. With Supabase, a Realtime subscription on the
 * `jobs` row replaces the polling without changing callers (DECISIONS D2).
 */
import { api, unwrap, type Schemas } from './client';

export type Job = Schemas['JobOut'];

export async function waitForJob(
  jobId: string,
  {
    intervalMs = 1000,
    timeoutMs = 120_000,
    onProgress,
  }: { intervalMs?: number; timeoutMs?: number; onProgress?: (job: Job) => void } = {},
): Promise<Job> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const job = unwrap(await api.GET('/v1/jobs/{job_id}', { params: { path: { job_id: jobId } } }));
    onProgress?.(job);
    if (job.status === 'succeeded' || job.status === 'failed') return job;
    if (Date.now() > deadline)
      throw new Error('This is taking longer than usual. Pull down to try again.');
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
