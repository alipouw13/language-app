import { useState, useCallback } from 'react';
import type { ConversationTurn } from '../types';
import { sendMessage, startConversation } from '../services/api';

interface ConversationState {
  conversationId: string | null;
  turns: ConversationTurn[];
  loading: boolean;
  error: string | null;
}

export function useConversationStore() {
  const [state, setState] = useState<ConversationState>({
    conversationId: null,
    turns: [],
    loading: false,
    error: null,
  });

  const start = useCallback(async (language: string, scenario?: string) => {
    setState((s) => ({ ...s, loading: true, error: null, turns: [] }));
    try {
      const res = await startConversation(language, scenario);
      setState((s) => ({ ...s, conversationId: res.id, loading: false }));
      return res.id;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start conversation';
      setState((s) => ({ ...s, loading: false, error: msg }));
      return null;
    }
  }, []);

  const send = useCallback(async (text: string) => {
    if (!state.conversationId) return;
    const nextIndex = state.turns.length;

    setState((s) => ({
      ...s,
      loading: true,
      error: null,
      turns: [...s.turns, { role: 'user', text, turn_index: nextIndex }],
    }));

    try {
      const res = await sendMessage(state.conversationId, text);
      setState((s) => ({
        ...s,
        loading: false,
        turns: [
          ...s.turns,
          { role: 'assistant', text: res.reply, turn_index: nextIndex + 1 },
        ],
      }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send message';
      setState((s) => ({ ...s, loading: false, error: msg }));
    }
  }, [state.conversationId, state.turns.length]);

  const reset = useCallback(() => {
    setState({ conversationId: null, turns: [], loading: false, error: null });
  }, []);

  const addTurn = useCallback((turn: ConversationTurn) => {
    setState((s) => ({ ...s, turns: [...s.turns, turn] }));
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    setState((s) => ({ ...s, loading }));
  }, []);

  const setError = useCallback((error: string | null) => {
    setState((s) => ({ ...s, error }));
  }, []);

  return { ...state, start, send, reset, addTurn, setLoading, setError };
}
