import { useEffect, useState } from 'react';
import type { LangCode, Level } from '../constants';
import { GRAMMAR_OPTIONS, LANGUAGES, LEVELS } from '../constants';
import type { VerbOption, VerbWorksheetRequest, Worksheet } from '../types';
import { generateVerbWorksheet, listVerbs } from '../services/api';
import WorksheetView from '../components/WorksheetView';
import { Alert, Button, Card, Field, Select, Spinner, TextInput } from '../components/ui';

export default function VerbPracticePage() {
  const [language, setLanguage] = useState<LangCode>('fr');
  const [nativeLanguage, setNativeLanguage] = useState<LangCode>('en');
  const [verbs, setVerbs] = useState<VerbOption[]>([]);
  const [verb, setVerb] = useState('');
  const [tense, setTense] = useState('');
  const [difficulty, setDifficulty] = useState<Level>('A2');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [worksheet, setWorksheet] = useState<Worksheet | null>(null);
  const [exerciseIds, setExerciseIds] = useState<string[]>([]);

  useEffect(() => {
    setTense('');
    setVerb('');
    let active = true;
    listVerbs(language)
      .then((v) => active && setVerbs(v))
      .catch(() => active && setVerbs([]));
    return () => {
      active = false;
    };
  }, [language]);

  const generate = async () => {
    if (!verb.trim()) return;
    setLoading(true);
    setError(null);
    setWorksheet(null);
    setExerciseIds([]);

    const req: VerbWorksheetRequest = {
      verb: verb.trim(),
      target_language: language,
      native_language: nativeLanguage,
      difficulty,
      ...(tense ? { grammar_focus: tense } : {}),
    };
    try {
      const res = await generateVerbWorksheet(req);
      setWorksheet(res.worksheet);
      setExerciseIds(res.exercise_ids ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>Verb practice</h1>
        <p className="muted">
          Pick a verb and drill its conjugations, translations and use in real
          sentences and conversations.
        </p>
      </header>

      <Card>
        <div className="grid-2">
          <Field label="Target language" htmlFor="vlang">
            <Select
              id="vlang"
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
          <Field label="Your language" htmlFor="nlang" hint="Translation exercises use this">
            <Select
              id="nlang"
              value={nativeLanguage}
              onChange={(e) => setNativeLanguage(e.target.value as LangCode)}
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="grid-2">
          <Field label="Choose a common verb" htmlFor="verbpick">
            <Select
              id="verbpick"
              value={verbs.some((v) => v.verb === verb) ? verb : ''}
              onChange={(e) => setVerb(e.target.value)}
            >
              <option value="">— Pick a verb —</option>
              {verbs.map((v) => (
                <option key={v.verb} value={v.verb}>
                  {v.verb} · {v.gloss}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="…or type any verb" htmlFor="verbtype">
            <TextInput
              id="verbtype"
              placeholder="e.g., apprendre"
              value={verb}
              onChange={(e) => setVerb(e.target.value)}
            />
          </Field>
        </div>

        <div className="grid-2">
          <Field label="Tense (optional)" htmlFor="vtense">
            <Select id="vtense" value={tense} onChange={(e) => setTense(e.target.value)}>
              {GRAMMAR_OPTIONS[language].map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Difficulty (CEFR)" htmlFor="vlevel">
            <Select
              id="vlevel"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as Level)}
            >
              {LEVELS.map((lv) => (
                <option key={lv} value={lv}>
                  {lv}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="actions">
          <Button onClick={generate} disabled={loading || !verb.trim()}>
            {loading ? <Spinner label="Generating…" /> : 'Generate verb worksheet'}
          </Button>
        </div>
      </Card>

      {error && <Alert>{error}</Alert>}
      {worksheet && (
        <WorksheetView worksheet={worksheet} lang={language} exerciseIds={exerciseIds} />
      )}
    </div>
  );
}
