import { useState, useRef, useEffect } from 'react';
import { useConversationStore } from '../state/useConversationStore';

const LANGUAGES = [
  { code: 'fr', label: 'French' },
  { code: 'es', label: 'Spanish' },
  { code: 'en', label: 'English' },
] as const;

export default function ConversationPage() {
  const { conversationId, turns, loading, error, start, send, reset } =
    useConversationStore();

  const [language, setLanguage] = useState('fr');
  const [scenario, setScenario] = useState('');
  const [input, setInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  const handleStart = async () => {
    await start(language, scenario || undefined);
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    const text = input;
    setInput('');
    await send(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        // Convert to base64 for WebSocket transmission (future use)
        const _reader = new FileReader();
        _reader.readAsDataURL(blob);
        // For now, just indicate recording completed
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      console.error('Microphone access denied');
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setIsRecording(false);
  };

  if (!conversationId) {
    return (
      <div>
        <h2>Voice Conversation Practice</h2>
        <div className="card">
          <div className="form-group">
            <label>Target Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Scenario (optional)</label>
            <input
              placeholder="e.g., At a train station in Madrid"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            />
          </div>
          <button onClick={handleStart} disabled={loading}>
            {loading ? 'Starting…' : 'Start Conversation'}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>
          Conversation{' '}
          <span className={`badge badge-${language}`}>
            {LANGUAGES.find((l) => l.code === language)?.label}
          </span>
        </h2>
        <button onClick={reset} style={{ background: '#6c757d' }}>
          End &amp; New
        </button>
      </div>

      <div className="chat-window">
        {turns.map((turn, i) => (
          <div key={i} className={`chat-bubble ${turn.role}`}>
            {turn.text}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble assistant" style={{ opacity: 0.6 }}>
            Typing…
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {error && <p className="error">{error}</p>}

      <div className="chat-input-row">
        <input
          placeholder="Type your message…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>
          Send
        </button>
        <button
          onClick={isRecording ? stopRecording : startRecording}
          style={{
            background: isRecording ? '#dc3545' : '#28a745',
            minWidth: '40px',
          }}
          title={isRecording ? 'Stop recording' : 'Start recording'}
        >
          {isRecording ? '⏹' : '🎤'}
        </button>
      </div>
    </div>
  );
}
