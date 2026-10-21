import { formatCount, formatDuration, updatedAgo } from '../format';

describe('formatCount', () => {
  it('matches the prototype', () => {
    expect(formatCount(504)).toBe('504');
    expect(formatCount(1189)).toBe('1.2K');
    expect(formatCount(6739)).toBe('6.7K');
    expect(formatCount(1000)).toBe('1K');
    expect(formatCount(90_000)).toBe('90K');
    expect(formatCount(104_000)).toBe('104K');
    expect(formatCount(127_146)).toBe('127K');
    expect(formatCount(1_250_000)).toBe('1.3M');
  });

  it('keeps unknown counts unknown (shown as a dash), never zero', () => {
    expect(formatCount(null)).toBeNull();
    expect(formatCount(undefined)).toBeNull();
    expect(formatCount(0)).toBe('0');
  });
});

describe('formatDuration', () => {
  it('formats seconds as m:ss', () => {
    expect(formatDuration(32)).toBe('0:32');
    expect(formatDuration(75.4)).toBe('1:15');
    expect(formatDuration(null)).toBe('');
  });
});

describe('updatedAgo', () => {
  it('reads like the prototype', () => {
    const now = new Date('2027-08-23T10:00:00Z');
    expect(updatedAgo('2027-08-23T08:00:00Z', now)).toBe('Updated 2 hours ago');
    expect(updatedAgo('2027-08-23T09:30:00Z', now)).toBe('Updated less than an hour ago');
    expect(updatedAgo('2027-08-21T09:00:00Z', now)).toBe('Updated 2 days ago');
  });
});
