// History list hook for the chat sidebar.
//
// Wraps GET /api/chat/conversations into a TanStack Query so the
// ChatPanel can show past conversations + a "new chat" button. The
// endpoint already returns rows sorted newest-first.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface ConversationSummary {
  conversation_id: string;
  last_message_at: string;
  title: string | null;
}

export const conversationListKey = ["chat", "conversations"] as const;

export function useConversationList(): UseQueryResult<ConversationSummary[]> {
  return useQuery<ConversationSummary[]>({
    queryKey: conversationListKey,
    queryFn: () => apiFetch<ConversationSummary[]>("/chat/conversations"),
    // The list is cheap to refetch and shouldn't lag behind the live
    // conversation; refetch on window focus.
    refetchOnWindowFocus: true,
    staleTime: 30 * 1000,
  });
}
