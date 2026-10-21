import { fireEvent, render, screen } from '@testing-library/react-native';

import { MatchCard } from '../MatchCard';

const mockMutate = jest.fn();
const mockShowToast = jest.fn();
let mockMatches: unknown[] = [];

jest.mock('@/api/hooks', () => ({
  useMatches: () => ({ data: mockMatches }),
  useDecideMatch: () => ({ mutate: mockMutate, isPending: false, isError: false }),
}));
jest.mock('@/state/app', () => ({
  useApp: (pick: (s: { showToast: typeof mockShowToast }) => unknown) =>
    pick({ showToast: mockShowToast }),
}));

const match = {
  id: 'm1',
  reel_id: 'r1',
  reel_title: 'One outfit, three Ganpati moods',
  posted_at: '2027-08-24T10:30:00Z',
  simulation_id: 's1',
  simulation_score: 52,
  project_id: null,
  project_title: null,
  reasons: ['You posted it 1 day after simulating it.'],
  status: 'pending',
};

beforeEach(() => {
  mockMutate.mockReset();
  mockShowToast.mockReset();
});

describe('MatchCard (logic doc §15: the creator confirms the match)', () => {
  it('shows nothing when no posted reel waits for an answer', async () => {
    mockMatches = [];
    await render(<MatchCard />);
    expect(screen.queryByText(/reel you simulated/)).toBeNull();
  });

  it('asks about the newest match, with the reasons Curo gave', async () => {
    mockMatches = [match];
    await render(<MatchCard />);
    expect(
      screen.getByText('Is “One outfit, three Ganpati moods” the reel you simulated?'),
    ).toBeTruthy();
    expect(screen.getByText('You posted it 1 day after simulating it.')).toBeTruthy();
  });

  it('confirms, then says what changes', async () => {
    mockMatches = [match];
    mockMutate.mockImplementation((_vars, opts) => opts.onSuccess());
    await render(<MatchCard />);
    await fireEvent.press(screen.getByLabelText('Yes, that’s it'));
    expect(mockMutate).toHaveBeenCalledWith({ id: 'm1', confirm: true }, expect.anything());
    expect(mockShowToast).toHaveBeenCalledWith(expect.stringMatching(/compares the reel/));
  });

  it('turns a wrong match down', async () => {
    mockMatches = [match];
    await render(<MatchCard />);
    await fireEvent.press(screen.getByLabelText('No'));
    expect(mockMutate).toHaveBeenCalledWith({ id: 'm1', confirm: false }, expect.anything());
  });

  it('names the draft when the reel matched a draft rather than a simulation', async () => {
    mockMatches = [
      { ...match, simulation_id: null, project_id: 'p1', project_title: 'Ganpati looks' },
    ];
    await render(<MatchCard />);
    expect(
      screen.getByText(
        'Did “One outfit, three Ganpati moods” come from your draft “Ganpati looks”?',
      ),
    ).toBeTruthy();
  });
});
