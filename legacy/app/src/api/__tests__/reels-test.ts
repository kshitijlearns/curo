import { toReelVM } from '../reels';

const card = {
  id: 'r1',
  shortcode: 'abc',
  title: 'GRWM: monsoon office look',
  tone: 2,
  duration_s: 34,
  permalink: 'https://www.instagram.com/reel/abc/',
  posted_at: '2027-08-18T10:00:00Z',
  metrics: { views: 48581, likes: null, comments: 181, shares: 102 },
  changes: null,
  compared_with: null,
  snapshots: 3,
  last_snapshot_at: '2027-08-23T04:00:00Z',
  seen_late: false,
};

describe('toReelVM', () => {
  it('keeps hidden counts unknown (null → shown as a dash), never zero', () => {
    const vm = toReelVM(card as never);
    expect(vm.metrics.likes).toEqual({ value: null, change: null });
    expect(vm.metrics.views.value).toBe('49K');
    expect(vm.metrics.comments.value).toBe('181');
    expect(vm.duration).toBe('0:34');
  });

  it('passes arrows through only when the API compared against something', () => {
    const vm = toReelVM({
      ...card,
      changes: { views: 32, likes: null, comments: -4, shares: 0 },
      compared_with: 'usual',
    } as never);
    expect(vm.metrics.views.change).toBe(32);
    expect(vm.metrics.likes.change).toBeNull();
    expect(vm.comparedWith).toBe('usual');
  });
});
