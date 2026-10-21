class Component extends DCLogic {
  constructor(props) { super(props); this.state = { local: null }; }
  go(tab) {
    if (typeof this.props.navHandler === 'function') this.props.navHandler(tab);
    else this.setState({ local: tab });
  }
  renderVals() {
    const active = (this.state.local && typeof this.props.navHandler !== 'function') ? this.state.local : (this.props.active ?? 'home');
    const items = [['home', 'Home'], ['studio', 'Studio'], ['sim', 'Simulator']].map(([id, label]) => {
      const on = active === id;
      return {
        label, current: on ? 'page' : 'false',
        isHome: id === 'home', isStudio: id === 'studio', isSim: id === 'sim',
        size: on ? 52 : 32, lift: on ? -30 : 0,
        bg: on ? '#5B73F2' : 'transparent', fg: on ? '#FFFFFF' : 'rgba(36,36,36,.72)',
        ring: on ? '0 0 0 6px #FFFFFF, 0 0 0 7px #E4E4EC' : 'none',
        weight: on ? 600 : 400, labelColor: on ? '#242424' : 'rgba(36,36,36,.72)',
        go: () => this.go(id)
      };
    });
    return { items };
  }
}