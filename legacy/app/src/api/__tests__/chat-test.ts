import { parseSSE, sourceLabel } from '../chat';

describe('the streamed reply', () => {
  it('reads complete events and keeps a half-arrived one for later', () => {
    const { events, rest } = parseSSE(
      'event: meta\ndata: {"intent":"explain","handoff":null}\n\nevent: delta\ndata: {"text":"It got 1.66×"}\n\nevent: del',
    );
    expect(events).toEqual([
      { event: 'meta', data: { intent: 'explain', handoff: null } },
      { event: 'delta', data: { text: 'It got 1.66×' } },
    ]);
    expect(rest).toBe('event: del');
  });

  it('skips a malformed event rather than failing the reply', () => {
    const { events } = parseSSE(
      'event: delta\ndata: {oops\n\nevent: done\ndata: {"text":"ok"}\n\n',
    );
    expect(events).toEqual([{ event: 'done', data: { text: 'ok' } }]);
  });

  it('names the record a source points to', () => {
    expect(sourceLabel({ kind: 'reel', id: 'r1', title: 'One kurta, five dupattas' })).toBe(
      'Your reel · One kurta, five dupattas',
    );
  });
});
