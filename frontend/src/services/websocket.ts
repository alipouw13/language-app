/**
 * WebSocket client for voice conversation streaming.
 *
 * Protocol:
 *   Send: { type: "audio"|"text", data: string, language: string }
 *   Recv: { type: "transcript"|"reply"|"error", text?, audio?, message? }
 *
 * The Entra access token (when auth is enabled) is passed as a `token` query
 * parameter, which the backend validates on connect.
 */
import { acquireToken } from '../auth/msal';

export type WsMessage =
  | { type: 'transcript'; text: string }
  | { type: 'reply'; text: string; audio?: string }
  | { type: 'error'; message: string };

export async function createConversationSocket(
  conversationId: string,
  onMessage: (msg: WsMessage) => void,
  onClose?: () => void,
): Promise<{
  send: (msg: { type: string; data: string; language: string }) => void;
  close: () => void;
}> {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  const token = await acquireToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : '';
  const ws = new WebSocket(
    `${protocol}://${host}/api/conversations/${conversationId}/ws${query}`,
  );

  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data) as WsMessage);
    } catch {
      console.error('Invalid WS message', event.data);
    }
  };
  ws.onclose = () => onClose?.();
  ws.onerror = (err) => console.error('WS error', err);

  return {
    send: (msg) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
    },
    close: () => ws.close(),
  };
}
