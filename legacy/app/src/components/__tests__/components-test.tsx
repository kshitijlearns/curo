import { fireEvent, render, screen } from '@testing-library/react-native';

import { Composer } from '../Composer';
import { Nav } from '../Nav';
import { Metric } from '../ui';

// @testing-library/react-native v14: render and fireEvent are async.

describe('Nav', () => {
  it('marks the active tab and reports taps', async () => {
    const onNav = jest.fn();
    await render(<Nav active="studio" onNav={onNav} />);
    expect(screen.getByLabelText('Studio')).toHaveProp('accessibilityState', { selected: true });
    expect(screen.getByLabelText('Home')).toHaveProp('accessibilityState', { selected: false });
    await fireEvent.press(screen.getByLabelText('Simulator'));
    expect(onNav).toHaveBeenCalledWith('sim');
  });
});

describe('Composer', () => {
  it('sends trimmed text and clears the box', async () => {
    const onSend = jest.fn();
    await render(<Composer placeholder="Ask Curo…" onSend={onSend} />);
    await fireEvent.changeText(screen.getByLabelText('Message Curo'), '  make it shorter  ');
    await fireEvent.press(screen.getByLabelText('Send'));
    expect(onSend).toHaveBeenCalledWith('make it shorter');
    expect(screen.getByLabelText('Message Curo')).toHaveProp('value', '');
  });

  it('does not send while busy', async () => {
    const onSend = jest.fn();
    await render(<Composer placeholder="Ask Curo…" onSend={onSend} busy />);
    await fireEvent.changeText(screen.getByLabelText('Message Curo'), 'hello');
    await fireEvent.press(screen.getByLabelText('Send'));
    expect(onSend).not.toHaveBeenCalled();
  });

  it('explains when voice input is unavailable (Expo Go)', async () => {
    const onNotice = jest.fn();
    await render(<Composer placeholder="Ask Curo…" onSend={jest.fn()} onNotice={onNotice} />);
    await fireEvent.press(screen.getByLabelText('Speak instead of typing'));
    expect(onNotice).toHaveBeenCalledWith(expect.stringMatching(/keyboard/));
  });
});

describe('Metric', () => {
  it('shows a dash, never a zero, when a count is not public', async () => {
    await render(<Metric kind="likes" value={null} change={null} />);
    expect(screen.getByText('–')).toBeTruthy();
    expect(screen.queryByText('0')).toBeNull();
  });

  it('shows a flat dash for changes within ±5%', async () => {
    await render(<Metric kind="views" value="41K" change={-4} />);
    expect(screen.getAllByText('–')).toHaveLength(1);
  });

  it('shows the size of a real change', async () => {
    await render(<Metric kind="shares" value="281" change={35} />);
    expect(screen.getByText('35%')).toBeTruthy();
  });
});
