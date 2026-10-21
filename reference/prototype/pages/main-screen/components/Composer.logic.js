class Component extends DCLogic {
  constructor(props) { super(props); this.state = { text: '', listening: false }; this.t = null; }
  componentWillUnmount() { if (this.t) clearTimeout(this.t); }
  submit(value) {
    const v = String(value || '').trim();
    if (!v || this.props.busy) return;
    if (typeof this.props.sendHandler === 'function') this.props.sendHandler(v);
    this.setState({ text: '', listening: false });
  }
  renderVals() {
    const s = this.state;
    const canSend = !!s.text.trim() && !this.props.busy;
    return {
      text: s.text,
      placeholder: this.props.placeholder ?? 'Describe your own idea…',
      onText: (e) => this.setState({ text: e.target.value }),
      onKey: (e) => { if (e.key === 'Enter') { e.preventDefault(); this.submit(this.state.text); } },
      send: () => this.submit(this.state.text),
      cantSend: !canSend, sendOpacity: canSend ? 1 : 0.4, sendScale: canSend ? 1 : 0.9,
      hint: this.props.hint ?? '',
      hasHint: !!(this.props.hint ?? ''),
      listening: s.listening, notListening: !s.listening,
      micLabel: s.listening ? 'Stop voice input' : 'Speak instead of typing',
      micBg: s.listening ? '#242424' : 'transparent', micFg: s.listening ? '#FFFFFF' : '#242424',
      micScale: s.listening ? 1.06 : 1,
      micAnim: s.listening ? 'curoPulse 1.2s ease-out infinite' : 'none',
      bars: Array.from({ length: 14 }, (_, i) => ({ d: (i * 97) % 900, c: i % 3 === 1 ? '#5B73F2' : '#242424' })),
      toggleMic: () => {
        if (this.state.listening) { if (this.t) clearTimeout(this.t); this.setState({ listening: false }); return; }
        this.setState({ listening: true });
        if (this.t) clearTimeout(this.t);
        this.t = setTimeout(() => this.setState({ listening: false, text: this.props.voiceSample ?? 'Something quick I can shoot at home' }), 1900);
      }
    };
  }
}