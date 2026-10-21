/**
 * The app's one React Query client. The root layout provides it to screens; the Studio's
 * store actions use it directly to keep a project's cached state current after each step.
 */
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});
