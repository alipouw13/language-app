import { useEffect, useRef, useState } from 'react';
import type { LangCode } from '../constants';
import { LANGUAGES } from '../constants';
import { useConversationStore } from '../state/useConversationStore';
import { authHeader } from '../services/api';
import InteractiveText from '../components/InteractiveText';
import { Alert, Button, Card, Field, LanguageBadge, Select, TextInput } from '../components/ui';

export default function ConversationPage() {
  const { conversationId, turns, loading, error, start, send, reset } =
    useConversationStore();

  const [language, setLanguage] = useState<LangCode>('fr');
  const [scenario, setScenario] = useState('');
  const [input, setInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.stop();
      }
    };
  }, []);

  const handleSend = async () => {
    if (!input.trim()) return;
    const text = input;
    setInput('');
    await send(text);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4';

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const ext = mimeType.includes('webm') ? 'webm' : 'mp4';
        const audioBlob = new Blob(chunksRef.current, { type: mimeType });

        const formData = new FormData();
        formData.append('audio', audioBlob, `recording.${ext}`);
        formData.append('language', language);

        setTranscribing(true);
        try {
          const res = await fetch('/api/speech/transcribe', {
            method: 'POST',
            headers: await authHeader(),
            body: formData,
          });
          if (!res.ok) throw new Error((await res.text()) || res.statusText);
          const data = await res.json();
          if (data.text) setInput((prev) => (prev ? `${prev} ${data.text}` : data.text));
        } catch (err) {
          console.error('Transcription failed:', err);
          alert('Failed to transcribe audio. Check the backend logs for details.');
        } finally {
          setTranscribing(false);
        }
      };

      recorder.start();
      recorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      console.error('Microphone error:', err);
      alert('Could not access your microphone. Grant permission and try again.');
    }
  };

  const stopRecording = () => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
    recorderRef.current = null;
    setIsRecording(false);
  };

  if (!conversationId) {
    return (
      <div className="page">
        <header className="page-head">
          <h1>Conversation practice</h1>
          <p className="muted">
            Chat by voice or text with an AI tutor that stays in your target language and
            corrects you gently.
          </p>
        </header>
        <Card>
          <Field label="Target language" htmlFor="clang">
            <Select
              id="clang"
              value={language}
              onChange={(e) => setLanguage(e.target.value as LangCode)}
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Scenario (optional)" htmlFor="cscen">
            <TextInput
              id="cscen"
              placeholder="e.g., At a train station in Madrid"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            />
          </Field>
          <div className="actions">
            <Button onClick={() => start(language, scenario || undefined)} disabled={loading}>
              {loading ? 'Starting…' : 'Start conversation'}
            </Button>
          </div>
          {error && <Alert>{error}</Alert>}
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-head row">
        <h1>
          Conversation <LanguageBadge code={language} />
        </h1>
        <Button variant="ghost" onClick={reset}>
          End &amp; new
        </Button>
      </header>

      <Card className="chat-card">
        <div className="chat-window">
          {turns.map((turn, i) => (
            <div key={i} className={`bubble ${turn.role}`}>
              <InteractiveText text={turn.text} lang={language} />
            </div>
          ))}
          {loading && <div className="bubble assistant typing">Typing…</div>}
          <div ref={chatEndRef} />
        </div>

        {error && <Alert>{error}</Alert>}

        <div className="chat-input">
          <TextInput
            placeholder={
              isRecording
                ? 'Recording… tap ⏹ when done'
                : transcribing
                  ? 'Transcribing…'
                  : 'Type your message…'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={loading || transcribing}
            readOnly={isRecording}
          />
          <Button onClick={handleSend} disabled={loading || !input.trim() || isRecording || transcribing}>
            Send
          </Button>
          <Button
            variant={isRecording ? 'danger' : 'success'}
            onClick={isRecording ? stopRecording : startRecording}
            title={isRecording ? 'Stop recording' : 'Start recording'}
          >
            {isRecording ? '⏹' : '🎤'}
          </Button>
        </div>
      </Card>
    </div>
  );
}
