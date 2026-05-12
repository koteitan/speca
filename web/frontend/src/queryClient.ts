import { QueryClient } from "@tanstack/react-query";

// Single shared QueryClient. Defaults tuned for a local SPA:
//   - 5 minute stale time is plenty for run / finding lists that rarely
//     change behind our back
//   - refetchOnWindowFocus is noisy on a local dev tool, off by default
//   - retry once: the backend is on localhost, network blips are rare
//   - gcTime longer than persister maxAge so persisted entries are not GC'd
//     out of memory mid-session
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 24 * 60 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
