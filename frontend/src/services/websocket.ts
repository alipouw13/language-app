/**
 * WebSocket client for voice conversation streaming.
 *
 * Protocol:
 *   Send: { type: "audio"|"text", data: string, language: string }
 *   Recv: { type: "transcript"|"reply"|"error", text?: string, audio?: string, message?: string }
 */

export type WsMessage =
  | { type: 'transcript'; text: string }
  | { type: 'reply'; text: string; audio?: string }
  | { type: 'error'; message: string };

export function createConversationSocket(
  conversationId: string,
  onMessage: (msg: WsMessage) => void,
  onClose?: () => void,
): {
  send: (msg: { type: string; data: string; language: string }) => void;
  close: () => void;
} {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  const ws = new WebSocket(`${protocol}://${host}/api/conversations/${conversationId}/ws`);

  ws.onmessage = (event) => {
    try {
      const msg: WsMessage = JSON.parse(event.data);
      onMessage(msg);
    } catch {
      console.error('Invalid WS message', event.data);
    }
  };

  ws.onclose = () => onClose?.();
  ws.onerror = (err) => console.error('WS error', err);

  const send = (msg: { type: string; data: string; language: string }) => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  };

  const close = () => ws.close();

  return { send, close };
}
