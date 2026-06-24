import { useEffect, useRef, useState } from 'react';
import type { LangCode, Level } from '../constants';
import { LANGUAGES, LEVELS } from '../constants';
import { useConversationStore } from '../state/useConversationStore';
import { authHeader, getNewsTopics, speakText } from '../services/api';
import type { NewsTopic } from '../types';
import InteractiveText from '../components/InteractiveText';
import SpeakButton from '../components/SpeakButton';
import { Alert, Badge, Button, Card, Field, LanguageBadge, Select, TextInput } from '../components/ui';

export default function ConversationPage() {
  const { conversationId, turns, loading, error, start, send, reset } =
    useConversationStore();

  const [language, setLanguage] = useState<LangCode>('fr');
  const [scenario, setScenario] = useState('');
  const [input, setInput] = useState('');
  const [autoSpeak, setAutoSpeak] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const lastSpokenRef = useRef(-1);

  // Current events (Real-Time Intelligence) topic picker.
  const [newsLevel, setNewsLevel] = useState<Level>('B1');
  const [personalized, setPersonalized] = useState(false);
  const [newsTopics, setNewsTopics] = useState<NewsTopic[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsError, setNewsError] = useState<string | null>(null);
  const [newsLoaded, setNewsLoaded] = useState(false);

  const [isRecording, setIsRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  // Auto-speak the assistant's latest reply so the learner hears pronunciation.
  useEffect(() => {
    if (!autoSpeak || turns.length === 0) return;
    const idx = turns.length - 1;
    const last = turns[idx];
    if (last.role === 'assistant' && idx > lastSpokenRef.current) {
      lastSpokenRef.current = idx;
      speakText(last.text, language).catch(() => undefined);
    }
  }, [turns, autoSpeak, language]);

  // Reset the spoken-index tracker when a new conversation starts.
  useEffect(() => {
    lastSpokenRef.current = -1;
  }, [conversationId]);

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

  const loadNews = async () => {
    setNewsLoading(true);
    setNewsError(null);
    try {
      const res = await getNewsTopics(language, newsLevel, personalized);
      setNewsTopics(res.items);
      setNewsLoaded(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load news';
      setNewsError(msg);
    } finally {
      setNewsLoading(false);
    }
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

        <Card>
          <header className="page-head">
            <h2>📰 Current events</h2>
            <p className="muted">
              Practice with real, fresh news in your target language. Pick a headline to start
              a conversation grounded in today's events.
            </p>
          </header>
          <div className="row" style={{ gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <Field label="Reading level" htmlFor="newslevel">
              <Select
                id="newslevel"
                value={newsLevel}
                onChange={(e) => setNewsLevel(e.target.value as Level)}
              >
                {LEVELS.map((lvl) => (
                  <option key={lvl} value={lvl}>
                    {lvl}
                  </option>
                ))}
              </Select>
            </Field>
            <label className="autospeak-toggle" title="Rank news toward skills you find hard">
              <input
                type="checkbox"
                checked={personalized}
                onChange={(e) => setPersonalized(e.target.checked)}
              />
              Personalize to my weak spots
            </label>
            <Button variant="ghost" onClick={loadNews} disabled={newsLoading}>
              {newsLoading ? 'Loading…' : "Load today's news"}
            </Button>
          </div>

          {newsError && <Alert>{newsError}</Alert>}

          {newsLoaded && !newsLoading && newsTopics.length === 0 && !newsError && (
            <p className="muted">
              No fresh news found for {LANGUAGES.find((l) => l.code === language)?.label}. Run the
              ingestion script (<code>python scripts/ingest_news.py</code>) to populate the
              Eventhouse, then try again.
            </p>
          )}

          <div className="news-list">
            {newsTopics.map((topic) => (
              <div key={topic.news_id} className="news-card">
                <div className="news-card-body">
                  <div className="row" style={{ gap: '0.5rem', alignItems: 'center' }}>
                    {topic.cefr_level && <Badge>{topic.cefr_level}</Badge>}
                    {topic.topic_tags.slice(0, 3).map((tag) => (
                      <span key={tag} className="chip">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <h3>{topic.title}</h3>
                  {topic.english_gloss && <p className="muted">{topic.english_gloss}</p>}
                  {topic.domain && <p className="news-source">{topic.domain}</p>}
                </div>
                <Button
                  onClick={() => start(language, undefined, topic.news_id)}
                  disabled={loading}
                >
                  Discuss this
                </Button>
              </div>
            ))}
          </div>
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
        <div className="head-actions">
          <label className="autospeak-toggle" title="Speak the tutor's replies aloud">
            <input
              type="checkbox"
              checked={autoSpeak}
              onChange={(e) => setAutoSpeak(e.target.checked)}
            />
            🔊 Auto-speak replies
          </label>
          <Button variant="ghost" onClick={reset}>
            End &amp; new
          </Button>
        </div>
      </header>

      <Card className="chat-card">
        <div className="chat-window">
          {turns.map((turn, i) => (
            <div key={i} className={`bubble-row ${turn.role}`}>
              <div className={`bubble ${turn.role}`}>
                <InteractiveText text={turn.text} lang={language} />
              </div>
              <SpeakButton
                text={turn.text}
                lang={language}
                title="Hear this sentence"
              />
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
