'use client';
/**
 * Ask Curo (Studio and Simulator): a streamed conversation. A change it hands to a Studio step
 * runs as a job; when that job finishes the screen refreshes. Each message counts against the
 * month's Ask Curo allowance; running out shows the upgrade screen.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

import { api, chatStream, waitForJob, type S } from '@/lib/api';

type Msg = { role: 'user' | 'assistant'; text: string };

export function useAskCuro(opts: {
  screen: S['ChatIn']['screen'];
  projectId?: string | null;
  simulationId?: string | null;
  onJobDone?: () => void;
}) {
  const qc = useQueryClient();
  const key = ['chat', opts.projectId ?? null, opts.simulationId ?? null];
  const history = useQuery({
    queryKey: key,
    queryFn: () => {
      const q = new URLSearchParams();
      if (opts.projectId) q.set('project_id', opts.projectId);
      if (opts.simulationId) q.set('simulation_id', opts.simulationId);
      return api<S['ChatMessageOut'][]>(`/chat?${q}`);
    },
    enabled: !!(opts.projectId || opts.simulationId),
  });
  const [live, setLive] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);

  const send = useCallback(
    async (text: string) => {
      setBusy(true);
      setLive((m) => [...m, { role: 'user', text }, { role: 'assistant', text: '' }]);
      const write = (t: (prev: string) => string) =>
        setLive((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: 'assistant', text: t(copy[copy.length - 1].text) };
          return copy;
        });
      try {
        for await (const { event, data } of chatStream({
          message: text,
          screen: opts.screen,
          project_id: opts.projectId ?? null,
          simulation_id: opts.simulationId ?? null,
          frame_id: null,
        })) {
          if (event === 'delta') write((p) => p + (data.text ?? ''));
          else if (event === 'reset') write(() => '');
          else if (event === 'done' && data?.text) write(() => data.text);
          else if (event === 'error') write(() => data?.message ?? 'Curo couldn’t answer just now.');
          else if (event === 'job' && data?.job_id) {
            waitForJob(data.job_id)
              .catch(() => undefined)
              .finally(() => opts.onJobDone?.());
          }
        }
      } catch (e) {
        write(() => (e instanceof Error ? e.message : 'Curo couldn’t answer just now.'));
      } finally {
        setBusy(false);
        qc.invalidateQueries({ queryKey: ['billing'] });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [opts.screen, opts.projectId, opts.simulationId],
  );

  const past: Msg[] = (history.data ?? []).map((m) => ({
    role: m.role === 'user' ? 'user' : 'assistant',
    text: m.content,
  }));
  return { messages: [...past, ...live], send, busy };
}

export function AskThread({ messages, busy }: { messages: Msg[]; busy: boolean }) {
  if (!messages.length) return null;
  return (
    <section aria-label="Ask Curo" className="card gray" style={{ marginTop: 18 }}>
      <h3 style={{ fontSize: 15 }}>Ask Curo</h3>
      <div className="stack" style={{ gap: 8 }} aria-live="polite">
        {messages.slice(-12).map((m, i) => (
          <div key={i} className={`bubble ${m.role === 'user' ? 'me' : 'them'}`} style={m.role === 'assistant' ? { background: 'var(--white)' } : undefined}>
            {m.text || (busy && i === messages.slice(-12).length - 1 ? '…' : '')}
          </div>
        ))}
      </div>
    </section>
  );
}
