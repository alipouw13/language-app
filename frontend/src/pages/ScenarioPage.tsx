import { useEffect, useState } from 'react';
import type { LangCode, Level } from '../constants';
import { GRAMMAR_OPTIONS, LANGUAGES, LEVELS } from '../constants';
import type { Worksheet, WorksheetRequest } from '../types';
import { generateWorksheet } from '../services/api';
import WorksheetView from '../components/WorksheetView';
import { Alert, Button, Card, Field, Select, Spinner, TextArea } from '../components/ui';

export default function ScenarioPage() {
  const [scenario, setScenario] = useState('');
  const [language, setLanguage] = useState<LangCode>('fr');
  const [grammarFocus, setGrammarFocus] = useState('');
  const [difficulty, setDifficulty] = useState<Level>('A2');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [worksheet, setWorksheet] = useState<Worksheet | null>(null);
  const [exerciseIds, setExerciseIds] = useState<string[]>([]);
  const [lessonId, setLessonId] = useState<string | null>(null);

  useEffect(() => setGrammarFocus(''), [language]);

  const generate = async () => {
    setLoading(true);
    setError(null);
    setWorksheet(null);
    setExerciseIds([]);
    setLessonId(null);

    const req: WorksheetRequest = {
      scenario,
      target_language: language,
      difficulty,
      ...(grammarFocus ? { grammar_focus: grammarFocus } : {}),
    };
    try {
      const res = await generateWorksheet(req);
      setWorksheet(res.worksheet);
      setExerciseIds(res.exercise_ids ?? []);
      setLessonId(res.lesson_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>Scenario worksheets</h1>
        <p className="muted">
          Generate a real-life practice worksheet with vocabulary, grammar notes and
          auto-graded exercises.
        </p>
      </header>

      <Card>
        <Field label="Scenario" htmlFor="scenario">
          <TextArea
            id="scenario"
            rows={3}
            placeholder="e.g., Ordering food in a Parisian café"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          />
        </Field>

        <div className="grid-2">
          <Field label="Target language" htmlFor="lang">
            <Select
              id="lang"
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
          <Field label="Difficulty (CEFR)" htmlFor="level">
            <Select
              id="level"
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

        <Field label="Grammar focus (optional)" htmlFor="grammar">
          <Select
            id="grammar"
            value={grammarFocus}
            onChange={(e) => setGrammarFocus(e.target.value)}
          >
            {GRAMMAR_OPTIONS[language].map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
        </Field>

        <div className="actions">
          <Button onClick={generate} disabled={loading || !scenario.trim()}>
            {loading ? <Spinner label="Generating…" /> : 'Generate worksheet'}
          </Button>
        </div>
      </Card>

      {error && <Alert>{error}</Alert>}
      {worksheet && (
        <WorksheetView
          worksheet={worksheet}
          lang={language}
          exerciseIds={exerciseIds}
          lessonId={lessonId}
        />
      )}
    </div>
  );
}
