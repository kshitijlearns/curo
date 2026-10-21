const THUMB_TONES = [
  { bg: '#5B73F2', fg: '#FFFFFF', beam: '#C3BFF2', leaf: '#242424', floor: '#C3BFF2', pot: '#F2D4E2' },
  { bg: '#F2D4E2', fg: '#242424', beam: '#FFFFFF', leaf: '#242424', floor: '#FFFFFF', pot: '#5B73F2' },
  { bg: '#C3BFF2', fg: '#242424', beam: '#FFFFFF', leaf: '#5B73F2', floor: '#E4E4EC', pot: '#242424' },
  { bg: '#242424', fg: '#FFFFFF', beam: '#5B73F2', leaf: '#C3BFF2', floor: '#5B73F2', pot: '#F2D4E2' }
];
class Component extends DCLogic {
  renderVals() {
    const n = THUMB_TONES.length;
    const t = THUMB_TONES[((Number(this.props.tone ?? 0) % n) + n) % n];
    return {
      bg: t.bg, fg: t.fg, beam: t.beam, leaf: t.leaf, floor: t.floor, pot: t.pot,
      title: this.props.title ?? '3 mistakes ruining your aesthetic reel',
      duration: this.props.duration ?? '0:32',
      titleSize: this.props.titleSize ?? 18,
      showText: !(this.props.compact ?? false),
      hcss: (this.props.height ?? null) ? this.props.height + 'px' : '100%'
    };
  }
}