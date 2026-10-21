import { Redirect } from 'expo-router';

import { useMe } from '@/api/hooks';
import { LoadingScreen, MessageScreen } from '@/components/PlainScreen';
import { Shell } from '@/screens/shell/Shell';
import { useSession } from '@/state/session';

/** Sign-in → onboarding → the app. */
export default function Index() {
  const session = useSession((s) => s.session);
  const me = useMe();

  if (!session) return <Redirect href="/login" />;
  if (me.isPending) return <LoadingScreen />;
  if (me.isError) {
    return (
      <MessageScreen
        title="Can’t reach Curo"
        text={`${me.error.message}. Check your connection, then try again.`}
        action={{ label: 'Try again', onPress: () => me.refetch() }}
      />
    );
  }
  // Home opens as soon as reels are in. A public account with no reels yet gets Home's
  // empty state once onboarding has finished, not another trip through onboarding.
  if (!me.data.onboarded) return <Redirect href="/onboarding" />;
  return <Shell />;
}
