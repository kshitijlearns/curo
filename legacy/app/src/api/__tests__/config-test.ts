import { apiBaseUrl } from '../config';

describe('apiBaseUrl', () => {
  it('uses EXPO_PUBLIC_API_BASE_URL when set, without a trailing slash', () => {
    expect(apiBaseUrl('https://api.curo.app/', '192.168.1.5:8081')).toBe('https://api.curo.app');
  });

  it('falls back to the dev machine Expo is served from, on port 8000', () => {
    expect(apiBaseUrl(undefined, '192.168.1.5:8081')).toBe('http://192.168.1.5:8000');
    expect(apiBaseUrl('  ', '10.0.0.7:8081')).toBe('http://10.0.0.7:8000');
  });

  it('uses localhost when there is no host (simulator, web)', () => {
    expect(apiBaseUrl(undefined, undefined)).toBe('http://localhost:8000');
  });
});
