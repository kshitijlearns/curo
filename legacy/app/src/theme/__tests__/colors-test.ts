import { colors, PALETTE } from '../colors';

describe('palette', () => {
  it('has exactly the six prototype colours', () => {
    expect([...PALETTE].sort()).toEqual(
      ['#5B73F2', '#C3BFF2', '#F2D4E2', '#FFFFFF', '#E4E4EC', '#242424'].sort(),
    );
  });

  it('derives muted text from ink only', () => {
    expect(colors.muted).toBe('rgba(36,36,36,0.72)');
  });

  it('defines no colour outside the palette except the derived muted ink', () => {
    const others = Object.entries(colors).filter(
      ([name, value]) => name !== 'muted' && !(PALETTE as readonly string[]).includes(value),
    );
    expect(others).toEqual([]);
  });
});
