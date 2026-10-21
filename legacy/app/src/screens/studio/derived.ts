import { useProject } from '@/api/hooks';
import { useApp } from '@/state/app';

/** What every Studio stage reads: the screen state and the project behind it. */
export function useStudio() {
  const st = useApp((s) => s.studio);
  const project = useProject(st.projectId).data ?? null;
  const idea = project?.idea ?? null;
  return {
    st,
    project,
    idea,
    beats: project?.script?.beats ?? [],
    frames: project?.storyboard?.frames ?? [],
    oppLabel: project?.opportunity?.name ?? st.oppName ?? 'Your own idea',
    validating: !st.projectId && !st.oppName && !st.busy,
  };
}
