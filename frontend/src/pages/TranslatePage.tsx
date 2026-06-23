import { useState } from 'react';
import type { LangCode } from '../constants';
import { LANGUAGES } from '../constants';
import type { TranslationResult } from '../types';
import { translateText } from '../services/api';
import InteractiveText from '../components/InteractiveText';
import { Alert, Button, Card, Field, LanguageBadge, Select, Spinner, TextArea } from '../components/ui';

const SOURCES: { code: 'auto' | LangCode; label: string }[] = [
  { code: 'auto', label: 'Auto-detect' },
  ...LANGUAGES.map((l) => ({ code: l.code, label: l.label })),
];

export default function TranslatePage() {
  const [text, setText] = useState('');
  const [source, setSource] = useState<'auto' | LangCode>('auto');
  const [targets, setTargets] = useState<LangCode[]>(['en', 'es']);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TranslationResult | null>(null);

  const toggleTarget = (code: LangCode) =>
    setTargets((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );

  const translate = async () => {
    if (!text.trim() || targets.length === 0) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await translateText(text, targets, source);
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Translation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>Translate</h1>
        <p className="muted">
          Powered by an Azure AI Foundry translation model (chat-model fallback in dev).
        </p>
      </header>

      <Card>
        <Field label="Text" htmlFor="ttext">
          <TextArea
            id="ttext"
            rows={4}
            placeholder="Type or paste text to translate…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>

        <div className="grid-2">
          <Field label="Source language" htmlFor="tsrc">
            <Select
              id="tsrc"
              value={source}
              onChange={(e) => setSource(e.target.value as 'auto' | LangCode)}
            >
              {SOURCES.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Translate into">
            <div className="checkrow">
              {LANGUAGES.map((l) => (
                <label key={l.code} className="checkpill">
                  <input
                    type="checkbox"
                    checked={targets.includes(l.code)}
                    onChange={() => toggleTarget(l.code)}
                  />
                  {l.label}
                </label>
              ))}
            </div>
          </Field>
        </div>

        <div className="actions">
          <Button onClick={translate} disabled={loading || !text.trim() || targets.length === 0}>
            {loading ? <Spinner label="Translating…" /> : 'Translate'}
          </Button>
        </div>
      </Card>

      {error && <Alert>{error}</Alert>}

      {result && (
        <Card>
          <p className="muted">
            Detected source: <strong>{result.source_language}</strong> · model:{' '}
            <code>{result.model}</code>
          </p>
          <div className="translation-grid">
            {Object.entries(result.translations).map(([code, value]) => (
              <div key={code} className="translation-item">
                <LanguageBadge code={code} />
                <p>
                  <InteractiveText text={value} lang={code} />
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
