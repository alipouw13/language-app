import { useState, useRef, useEffect } from 'react';
import { useConversationStore } from '../state/useConversationStore';
import {
  AudioConfig,
  SpeechConfig,
  SpeechRecognizer,
  ResultReason,
  CancellationReason,
} from 'microsoft-cognitiveservices-speech-sdk';

const LANGUAGES = [
  { code: 'fr', label: 'French' },
  { code: 'es', label: 'Spanish' },
  { code: 'en', label: 'English' },
] as const;

const LANGUAGE_LOCALE_MAP: Record<string, string> = {
  en: 'en-US',
  fr: 'fr-FR',
  es: 'es-ES',
};

// Azure Speech credentials — exposed via Vite env vars
const SPEECH_KEY = import.meta.env.VITE_AZURE_SPEECH_KEY ?? '';
const SPEECH_REGION = import.meta.env.VITE_AZURE_SPEECH_REGION ?? 'eastus2';

export default function ConversationPage() {
  const { conversationId, turns, loading, error, start, send, reset } =
    useConversationStore();

  const [language, setLanguage] = useState('fr');
  const [scenario, setScenario] = useState('');
  const [input, setInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const recognizerRef = useRef<SpeechRecognizer | null>(null);
  // Cumulative recognized (final) text and live interim text
  const recognisedTextRef = useRef('');
  const [recognisingText, setRecognisingText] = useState('');

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  // Keep the input field in sync with recognised + interim text while recording
  useEffect(() => {
    if (isRecording) {
      setInput(recognisedTextRef.current + recognisingText);
    }
  }, [recognisingText, isRecording]);

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
    if (!SPEECH_KEY) {
      alert(
        'Azure Speech key is not configured.\n\n' +
          'Create a frontend/.env file with:\n' +
          'VITE_AZURE_SPEECH_KEY=<your-key>\n' +
          'VITE_AZURE_SPEECH_REGION=<your-region>'
      );
      return;
    }

    try {
      // 1) Configure Azure Speech SDK
      const speechConfig = SpeechConfig.fromSubscription(SPEECH_KEY, SPEECH_REGION);
      speechConfig.speechRecognitionLanguage = LANGUAGE_LOCALE_MAP[language] || 'en-US';

      // 2) Use the SDK's built-in microphone support — most reliable in browser
      const audioConfig = AudioConfig.fromDefaultMicrophoneInput();

      // 3) Create recognizer
      const recognizer = new SpeechRecognizer(speechConfig, audioConfig);

      // Reset transcript state
      recognisedTextRef.current = '';
      setRecognisingText('');

      // Interim results (recognizing) — show live partial text
      recognizer.recognizing = (_s, e) => {
        console.log('[STT] Recognizing:', e.result.text);
        setRecognisingText(e.result.text);
      };

      // Final results (recognized) — accumulate confirmed text
      recognizer.recognized = (_s, e) => {
        setRecognisingText('');
        if (e.result.reason === ResultReason.RecognizedSpeech) {
          console.log('[STT] Recognized:', e.result.text);
          recognisedTextRef.current =
            recognisedTextRef.current === ''
              ? `${e.result.text} `
              : `${recognisedTextRef.current}${e.result.text} `;
          setInput(recognisedTextRef.current);
        } else if (e.result.reason === ResultReason.NoMatch) {
          console.log('[STT] No match — speech could not be recognized');
        }
      };

      recognizer.canceled = (_s, e) => {
        console.log(`[STT] Canceled: Reason=${e.reason}`);
        if (e.reason === CancellationReason.Error) {
          console.error(`[STT] Error: ${e.errorCode} — ${e.errorDetails}`);
          alert(`Speech recognition error: ${e.errorDetails}`);
        }
        recognizer.stopContinuousRecognitionAsync();
      };

      recognizer.sessionStopped = () => {
        console.log('[STT] Session stopped');
        recognizer.stopContinuousRecognitionAsync();
      };

      // 4) Start continuous recognition
      recognizer.startContinuousRecognitionAsync(
        () => {
          console.log('[STT] Continuous recognition started');
          recognizerRef.current = recognizer;
          setIsRecording(true);
        },
        (err) => {
          console.error('[STT] Failed to start recognition:', err);
          alert('Failed to start speech recognition. Check your Azure Speech configuration.');
        }
      );
    } catch (err) {
      console.error('[STT] Failed to create recognizer:', err);
      alert('Failed to start speech recognition. Please check your configuration.');
    }
  };

  const stopRecording = () => {
    const recognizer = recognizerRef.current;
    if (recognizer) {
      recognizer.stopContinuousRecognitionAsync(
        () => {
          console.log('[STT] Continuous recognition stopped');
          recognizer.close();
          recognizerRef.current = null;
        },
        (err) => {
          console.error('[STT] Error stopping recognition:', err);
          recognizerRef.current = null;
        }
      );
    }
    setIsRecording(false);
    setRecognisingText('');
    // The transcribed text stays in the input field for the user to review & send
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognizerRef.current) {
        recognizerRef.current.stopContinuousRecognitionAsync();
        recognizerRef.current.close();
      }
    };
  }, []);

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
          placeholder={isRecording ? 'Listening…' : 'Type your message…'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          readOnly={isRecording}
          style={isRecording ? { borderColor: '#dc3545', backgroundColor: '#fff5f5' } : undefined}
        />
        <button onClick={handleSend} disabled={loading || !input.trim() || isRecording}>
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
