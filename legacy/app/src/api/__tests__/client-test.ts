import { ApiError, OFFLINE, auth } from '../client';

type OnError = NonNullable<typeof auth.onError>;
const onError = auth.onError as OnError;
const call = (error: unknown) => onError({ error } as Parameters<OnError>[0]);

describe('a request that never got an answer', () => {
  it('reads as a plain sentence, not "Network request failed"', () => {
    const out = call(new TypeError('Network request failed'));
    expect(out).toBeInstanceOf(ApiError);
    expect((out as ApiError).message).toBe(OFFLINE);
  });

  it('leaves a cancelled request alone', () => {
    const aborted = Object.assign(new Error('aborted'), { name: 'AbortError' });
    expect(call(aborted)).toBe(aborted);
  });
});
