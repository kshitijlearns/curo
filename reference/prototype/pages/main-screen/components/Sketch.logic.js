class Component extends DCLogic {
  renderVals() {
    const k = this.props.kind ?? 'closeup';
    return {
      isCloseup: k === 'closeup', isFlatlay: k === 'flatlay', isLook1: k === 'look1', isLook2: k === 'look2', isLook3: k === 'look3',
      isRewind: k === 'rewind', isMirror: k === 'mirror', isCta: k === 'cta', isTriptych: k === 'triptych'
    };
  }
}