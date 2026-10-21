/**
 * Studio over the API (logic doc §9–§12). One project id carries the opportunity, the chosen
 * idea and every script, storyboard and caption version.
 *
 * Generation answers 202 with a job; `step` waits for it and returns the fresh project. Quick
 * steps (picking an idea, own script, hashtags, the chosen caption, saving) return it directly.
 */
import { api, unwrap, type Schemas } from './client';
import { waitForJob } from './jobs';
import { queryClient } from './queryClient';

export type Project = Schemas['Project'];
export type IdeaOut = Schemas['IdeaOut'];
export type Beat = Schemas['BeatOut'];
export type Frame = Schemas['FrameOutApi'];
export type Validation = Schemas['Validation'];

export const projectKey = (id: string) => ['projects', id] as const;

const path = (projectId: string) => ({ params: { path: { project_id: projectId } } });

export async function getProject(projectId: string): Promise<Project> {
  const project = unwrap(await api.GET('/v1/projects/{project_id}', path(projectId)));
  queryClient.setQueryData(projectKey(projectId), project);
  return project;
}

/** Follow a step's job to the end, then reload the project. A failed job's reason is the
 * error's message (e.g. "Write or generate the script first."). */
async function finish(res: { job_id: string; project_id: string }): Promise<Project> {
  const job = await waitForJob(res.job_id, { intervalMs: 600, timeoutMs: 180_000 });
  if (job.status === 'failed') throw new Error(job.error ?? 'That didn’t work. Try again.');
  return getProject(res.project_id);
}

function refreshSaved() {
  queryClient.invalidateQueries({ queryKey: ['saved'] });
  queryClient.invalidateQueries({ queryKey: ['me'] });
}

/** A project from an opportunity (its first three ideas are written straight away) or from
 * an idea the creator validated. */
export async function startProject(body: {
  opportunity_id?: string;
  idea_text?: string;
}): Promise<Project> {
  const started = unwrap(await api.POST('/v1/projects', { body }));
  if (started.job_id) return finish({ job_id: started.job_id, project_id: started.project_id });
  return getProject(started.project_id);
}

export async function newIdeas(projectId: string, prompt: string | null): Promise<Project> {
  return finish(
    unwrap(
      await api.POST('/v1/projects/{project_id}/ideas', { ...path(projectId), body: { prompt } }),
    ),
  );
}

export async function selectIdea(projectId: string, ideaId: string): Promise<Project> {
  const project = unwrap(
    await api.POST('/v1/projects/{project_id}/ideas/{idea_id}/select', {
      params: { path: { project_id: projectId, idea_id: ideaId } },
    }),
  );
  queryClient.setQueryData(projectKey(projectId), project);
  return project;
}

export async function writeScript(
  projectId: string,
  opts: { direction?: string | null; regenerate?: boolean } = {},
): Promise<Project> {
  return finish(
    unwrap(
      await api.POST('/v1/projects/{project_id}/script', {
        ...path(projectId),
        body: { direction: opts.direction ?? null, regenerate: !!opts.regenerate },
      }),
    ),
  );
}

export async function reviseScript(projectId: string, instruction: string): Promise<Project> {
  return finish(
    unwrap(
      await api.POST('/v1/projects/{project_id}/script/revise', {
        ...path(projectId),
        body: { instruction },
      }),
    ),
  );
}

export async function ownScript(projectId: string, text: string): Promise<Project> {
  const project = unwrap(
    await api.PUT('/v1/projects/{project_id}/script', { ...path(projectId), body: { text } }),
  );
  queryClient.setQueryData(projectKey(projectId), project);
  return project;
}

export async function buildStoryboard(projectId: string): Promise<Project> {
  return finish(unwrap(await api.POST('/v1/projects/{project_id}/storyboard', path(projectId))));
}

export async function reviseStoryboard(
  projectId: string,
  instruction: string,
  frameId: string | null,
): Promise<Project> {
  return finish(
    unwrap(
      await api.POST('/v1/projects/{project_id}/storyboard/revise', {
        ...path(projectId),
        body: { instruction, frame_id: frameId },
      }),
    ),
  );
}

export async function writeCaptions(projectId: string): Promise<Project> {
  return finish(unwrap(await api.POST('/v1/projects/{project_id}/captions', path(projectId))));
}

export async function reviseCaptions(projectId: string, instruction: string): Promise<Project> {
  return finish(
    unwrap(
      await api.POST('/v1/projects/{project_id}/captions/revise', {
        ...path(projectId),
        body: { instruction },
      }),
    ),
  );
}

export async function putHashtags(projectId: string, hashtags: string[]): Promise<Project> {
  const project = unwrap(
    await api.PUT('/v1/projects/{project_id}/hashtags', { ...path(projectId), body: { hashtags } }),
  );
  queryClient.setQueryData(projectKey(projectId), project);
  return project;
}

export async function chooseCaption(projectId: string, chosen: number): Promise<Project> {
  const project = unwrap(
    await api.PUT('/v1/projects/{project_id}/caption', { ...path(projectId), body: { chosen } }),
  );
  queryClient.setQueryData(projectKey(projectId), project);
  return project;
}

export async function saveDraft(projectId: string, step: Project['step']): Promise<Project> {
  const project = unwrap(
    await api.POST('/v1/projects/{project_id}/save', { ...path(projectId), body: { step } }),
  );
  queryClient.setQueryData(projectKey(projectId), project);
  refreshSaved();
  return project;
}

export async function validateIdea(text: string): Promise<Validation> {
  return unwrap(await api.POST('/v1/ideas/validate', { body: { text } }));
}

/** The current project, as last loaded or changed (Studio screens read it). */
export function cachedProject(projectId: string | null): Project | undefined {
  return projectId ? queryClient.getQueryData<Project>(projectKey(projectId)) : undefined;
}
