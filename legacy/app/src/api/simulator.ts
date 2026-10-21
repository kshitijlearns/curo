/**
 * The Simulator over the API (logic doc §13; MVP doc T9 and T15).
 *
 * Uploading: the API signs an upload URL and the video goes straight to storage (with local
 * storage the URL is on the API itself, given as a path). Simulating answers 202 with a job;
 * `runSimulation` follows it — its progress names the step the loading screen ticks off — and
 * returns the stored result. Applying an edit writes it back to the linked Studio draft; a
 * re-run takes the re-recorded video.
 */
import { api, unwrap, type Schemas } from './client';
import { apiBaseUrl } from './config';
import { waitForJob, type Job } from './jobs';
import { queryClient } from './queryClient';
import { getProject } from './studio';

export type Simulation = Schemas['Simulation'];
export type SimResult = Schemas['SimResult'];
export type SimEdit = Schemas['SimEdit'];
export type SimItem = Schemas['SimItem'];
export type SimReportRow = Schemas['SimReportRow'];
export type SampleVideo = Schemas['SampleVideo'];
export type Uploaded = Schemas['Uploaded'];
export type SimAudienceId = 'followers' | 'new' | 'both';

/** A video picked on the phone, ready to upload. */
export type PickedVideo = {
  uri: string;
  name: string;
  mimeType: string | null;
  durationS: number | null;
  width: number | null;
  height: number | null;
};

export const simulationKey = (id: string) => ['simulations', id] as const;
export const samplesKey = ['uploads', 'samples'] as const;
export const MAX_SECONDS = 90;

/** The job's steps, in the order the loading screen shows them (jobs/simulation.py). */
export const SIM_STEP_KEYS = ['understanding', 'dna', 'trend', 'compare', 'estimate'] as const;

export function stepOf(job: Job): number {
  if (job.status === 'succeeded') return SIM_STEP_KEYS.length;
  const i = SIM_STEP_KEYS.indexOf(job.progress?.step as (typeof SIM_STEP_KEYS)[number]);
  return i < 0 ? 0 : i;
}

export async function listSamples(): Promise<SampleVideo[]> {
  return unwrap(await api.GET('/v1/uploads/samples'));
}

/** Store one of the provider's sample recordings as the upload (the demo's takes). */
export async function uploadSample(name: string): Promise<Uploaded> {
  return unwrap(await api.POST('/v1/uploads/sample', { body: { name } }));
}

/** Send a picked video to storage through a signed upload URL. */
export async function uploadVideo(video: PickedVideo): Promise<Uploaded> {
  const contentType = video.mimeType === 'video/quicktime' ? 'video/quicktime' : 'video/mp4';
  const signed = unwrap(
    await api.POST('/v1/uploads/sign', { body: { content_type: contentType } }),
  );
  const blob = await (await fetch(video.uri)).blob();
  const url = signed.url.startsWith('/') ? `${apiBaseUrl()}${signed.url}` : signed.url;
  const failed = 'The upload didn’t finish. Check your connection and try again.';
  const res = await fetch(url, {
    method: signed.method,
    headers: signed.headers,
    body: blob,
  }).catch(() => {
    throw new Error(failed);
  });
  if (!res.ok) throw new Error(failed);
  return {
    path: signed.path,
    duration_s: video.durationS ?? 0,
    width: video.width,
    height: video.height,
    caption: null,
  };
}

export function cachedSimulation(id: string | null): Simulation | undefined {
  return id ? queryClient.getQueryData<Simulation>(simulationKey(id)) : undefined;
}

export async function getSimulation(id: string): Promise<Simulation> {
  const sim = unwrap(
    await api.GET('/v1/simulations/{simulation_id}', {
      params: { path: { simulation_id: id } },
    }),
  );
  queryClient.setQueryData(simulationKey(id), sim);
  return sim;
}

/** Follow a simulation's job to the end and return the stored simulation. A failure's reason
 * (e.g. "This video is 95 seconds long…") is the error's message. */
async function follow(
  started: { simulation_id: string; job_id: string },
  onStep?: (step: number) => void,
): Promise<Simulation> {
  const job = await waitForJob(started.job_id, {
    intervalMs: 500,
    timeoutMs: 240_000,
    onProgress: (j) => onStep?.(stepOf(j)),
  });
  const sim = await getSimulation(started.simulation_id);
  if (job.status === 'failed' || sim.status === 'failed')
    throw new Error(sim.error ?? job.error ?? 'Curo couldn’t finish this simulation.');
  return sim;
}

export async function runSimulation(
  body: {
    upload_path: string;
    project_id?: string | null;
    audience: SimAudienceId;
    caption?: string | null;
  },
  onStep?: (step: number) => void,
): Promise<Simulation> {
  return follow(unwrap(await api.POST('/v1/simulations', { body })), onStep);
}

export async function rerun(
  simulationId: string,
  body: { upload_path: string; caption?: string | null },
  onStep?: (step: number) => void,
): Promise<Simulation> {
  return follow(
    unwrap(
      await api.POST('/v1/simulations/{simulation_id}/rerun', {
        params: { path: { simulation_id: simulationId } },
        body,
      }),
    ),
    onStep,
  );
}

/** Accept an edit. With a linked draft it is written to the Studio script and storyboard;
 * this waits for that and refreshes the draft. */
export async function applyEdit(
  simulationId: string,
  editId: string,
  projectId: string | null,
): Promise<SimEdit> {
  const res = unwrap(
    await api.POST('/v1/simulations/{simulation_id}/edits/{edit_id}/apply', {
      params: { path: { simulation_id: simulationId, edit_id: editId } },
    }),
  );
  if (res.job_id) {
    const job = await waitForJob(res.job_id, { intervalMs: 600, timeoutMs: 180_000 });
    if (job.status === 'failed') throw new Error(job.error ?? 'That edit didn’t apply.');
    if (projectId) await getProject(projectId);
  }
  return res.edit;
}
