import { fireEvent, render, screen } from '@testing-library/react-native';

import Settings from '@/app/settings';

const mockDeleteAccount = jest.fn();
const mockReplace = jest.fn();

jest.mock(
  'react-native-safe-area-context',
  // jest.mock factories run before imports, so they load modules with require.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  () => require('react-native-safe-area-context/jest/mock').default,
);
jest.mock('expo-router', () => ({
  router: {
    replace: (...a: unknown[]) => mockReplace(...a),
    canGoBack: () => false,
    push: jest.fn(),
  },
}));
jest.mock('@tanstack/react-query', () => ({ useQueryClient: () => ({ clear: jest.fn() }) }));
jest.mock('@/state/session', () => ({
  useSession: (pick: (s: { signOut: () => void }) => unknown) => pick({ signOut: jest.fn() }),
}));
jest.mock('@/api/hooks', () => {
  const idle = { mutate: jest.fn(), isPending: false, isError: false };
  return {
    useMe: () => ({
      data: {
        email: 'demo@curo.local',
        reels: 50,
        creator: { ig_username: 'curo.demo' },
        account: { followers: 48000 },
      },
    }),
    usePeers: () => ({ data: { tracked: [], suggested: [] } }),
    useTrackPeers: () => idle,
    useRemovePeer: () => idle,
    useMemory: () => ({ data: [], isSuccess: true }),
    useDeleteMemory: () => idle,
    useDeleteAccount: () => ({ mutate: mockDeleteAccount, isPending: false, isError: false }),
  };
});

beforeEach(() => {
  mockDeleteAccount.mockReset();
  mockReplace.mockReset();
});

describe('Settings: deleting the account (logic doc §17)', () => {
  it('says what goes before anything is deleted', async () => {
    await render(<Settings />);
    await fireEvent.press(screen.getByLabelText('Delete account'));
    expect(mockDeleteAccount).not.toHaveBeenCalled();
    expect(screen.getByText(/stops collecting @curo\.demo/)).toBeTruthy();
    expect(screen.getByText(/can’t be undone/)).toBeTruthy();
  });

  it('can be called off', async () => {
    await render(<Settings />);
    await fireEvent.press(screen.getByLabelText('Delete account'));
    await fireEvent.press(screen.getByLabelText('Keep my account'));
    expect(screen.queryByText(/can’t be undone/)).toBeNull();
    expect(mockDeleteAccount).not.toHaveBeenCalled();
  });

  it('deletes on the second tap and returns to sign-in', async () => {
    mockDeleteAccount.mockImplementation((_v, opts) => opts.onSuccess());
    await render(<Settings />);
    await fireEvent.press(screen.getByLabelText('Delete account'));
    await fireEvent.press(screen.getByLabelText('Delete my account'));
    expect(mockDeleteAccount).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith('/login');
  });
});
