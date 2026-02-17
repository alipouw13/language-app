import { useState, useEffect } from 'react';
import type { Worksheet, WorksheetRequest } from '../types';
import { generateWorksheet, evaluateExercise } from '../services/api';

const LANGUAGES = [
  { code: 'fr', label: 'French' },
  { code: 'es', label: 'Spanish' },
  { code: 'en', label: 'English' },
] as const;

const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'] as const;

// Verb tenses organized by language
const GRAMMAR_OPTIONS: Record<'en' | 'fr' | 'es', { value: string; label: string }[]> = {
  en: [
    { value: '', label: '-- Select a tense --' },
    { value: 'simple present', label: 'Simple Present' },
    { value: 'present continuous', label: 'Present Continuous' },
    { value: 'simple past', label: 'Simple Past' },
    { value: 'past continuous', label: 'Past Continuous' },
    { value: 'present perfect', label: 'Present Perfect' },
    { value: 'past perfect', label: 'Past Perfect' },
    { value: 'simple future', label: 'Simple Future (will)' },
    { value: 'future with going to', label: 'Future (going to)' },
    { value: 'future perfect', label: 'Future Perfect' },
    { value: 'conditional', label: 'Conditional' },
    { value: 'conditional perfect', label: 'Conditional Perfect' },
    { value: 'imperative', label: 'Imperative' },
    { value: 'passive voice', label: 'Passive Voice' },
    { value: 'reported speech', label: 'Reported Speech' },
  ],
  fr: [
    { value: '', label: '-- Sélectionner un temps --' },
    { value: 'présent', label: 'Présent' },
    { value: 'passé composé', label: 'Passé Composé' },
    { value: 'imparfait', label: 'Imparfait' },
    { value: 'plus-que-parfait', label: 'Plus-que-parfait' },
    { value: 'passé simple', label: 'Passé Simple' },
    { value: 'passé antérieur', label: 'Passé Antérieur' },
    { value: 'futur simple', label: 'Futur Simple' },
    { value: 'futur antérieur', label: 'Futur Antérieur' },
    { value: 'conditionnel présent', label: 'Conditionnel Présent' },
    { value: 'conditionnel passé', label: 'Conditionnel Passé' },
    { value: 'subjonctif présent', label: 'Subjonctif Présent' },
    { value: 'subjonctif passé', label: 'Subjonctif Passé' },
    { value: 'subjonctif imparfait', label: 'Subjonctif Imparfait' },
    { value: 'impératif', label: 'Impératif' },
    { value: 'gérondif', label: 'Gérondif' },
  ],
  es: [
    { value: '', label: '-- Seleccionar un tiempo --' },
    { value: 'presente de indicativo', label: 'Presente de Indicativo' },
    { value: 'pretérito indefinido', label: 'Pretérito Indefinido' },
    { value: 'pretérito imperfecto', label: 'Pretérito Imperfecto' },
    { value: 'pretérito perfecto compuesto', label: 'Pretérito Perfecto Compuesto' },
    { value: 'pretérito pluscuamperfecto', label: 'Pretérito Pluscuamperfecto' },
    { value: 'pretérito anterior', label: 'Pretérito Anterior' },
    { value: 'futuro simple', label: 'Futuro Simple' },
    { value: 'futuro compuesto', label: 'Futuro Compuesto' },
    { value: 'condicional simple', label: 'Condicional Simple' },
    { value: 'condicional compuesto', label: 'Condicional Compuesto' },
    { value: 'presente de subjuntivo', label: 'Presente de Subjuntivo' },
    { value: 'imperfecto de subjuntivo', label: 'Imperfecto de Subjuntivo' },
    { value: 'pluscuamperfecto de subjuntivo', label: 'Pluscuamperfecto de Subjuntivo' },
    { value: 'imperativo', label: 'Imperativo' },
    { value: 'gerundio', label: 'Gerundio' },
  ],
};

export default function ScenarioPage() {
  const [scenario, setScenario] = useState('');
  const [language, setLanguage] = useState<'en' | 'fr' | 'es'>('fr');
  const [grammarFocus, setGrammarFocus] = useState('');
  const [difficulty, setDifficulty] = useState<(typeof LEVELS)[number]>('A2');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [worksheet, setWorksheet] = useState<Worksheet | null>(null);
  const [lessonId, setLessonId] = useState<string | null>(null);
  const [exerciseIds, setExerciseIds] = useState<string[]>([]);

  // Exercise answer tracking
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [evaluations, setEvaluations] = useState<
    Record<number, { is_correct: boolean; score: number; feedback: string }>
  >({});
  const [evaluating, setEvaluating] = useState<number | null>(null);

  // Reset grammar focus when language changes
  useEffect(() => {
    setGrammarFocus('');
  }, [language]);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setWorksheet(null);
    setAnswers({});
    setEvaluations({});
    setExerciseIds([]);

    const req: WorksheetRequest = {
      scenario,
      target_language: language,
      difficulty,
      ...(grammarFocus ? { grammar_focus: grammarFocus } : {}),
    };

    try {
      const res = await generateWorksheet(req);
      setWorksheet(res.worksheet);
      setLessonId(res.lesson_id);
      setExerciseIds(res.exercise_ids || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async (index: number, exerciseId: string) => {
    const answer = answers[index];
    if (!answer?.trim()) return;
    setEvaluating(index);
    try {
      const result = await evaluateExercise(exerciseId, answer);
      setEvaluations((prev) => ({ ...prev, [index]: result }));
    } catch {
      setEvaluations((prev) => ({
        ...prev,
        [index]: { is_correct: false, score: 0, feedback: 'Evaluation failed' },
      }));
    } finally {
      setEvaluating(null);
    }
  };

  return (
    <div>
      <h2>Scenario Worksheet Generator</h2>

      <div className="card">
        <div className="form-group">
          <label>Scenario</label>
          <textarea
            rows={3}
            placeholder="e.g., Ordering food in a Parisian café"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Target Language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value as 'en' | 'fr' | 'es')}>
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Difficulty</label>
            <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as (typeof LEVELS)[number])}>
              {LEVELS.map((lv) => (
                <option key={lv} value={lv}>
                  {lv}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Grammar Focus (optional)</label>
          <select
            value={grammarFocus}
            onChange={(e) => setGrammarFocus(e.target.value)}
          >
            {GRAMMAR_OPTIONS[language].map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <button onClick={handleGenerate} disabled={loading || !scenario.trim()}>
          {loading ? 'Generating…' : 'Generate Worksheet'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {worksheet && (
        <div className="card">
          <h2>{worksheet.scenario_summary}</h2>
          <p>
            <strong>Grammar Focus:</strong> {worksheet.grammar_focus}
          </p>

          <h3>Explanation</h3>
          <p>{worksheet.explanations}</p>

          <h3>Vocabulary</h3>
          <table className="vocab-table">
            <thead>
              <tr>
                <th>Word</th>
                <th>Translation</th>
                <th>Example</th>
              </tr>
            </thead>
            <tbody>
              {worksheet.vocabulary.map((v, i) => (
                <tr key={i}>
                  <td><strong>{v.word}</strong></td>
                  <td>{v.translation}</td>
                  <td><em>{v.example_sentence}</em></td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Exercises</h3>
          {worksheet.exercises.map((ex, i) => (
            <div key={i} className="exercise-card">
              <span className="type-badge">{ex.type.replace('_', ' ')}</span>
              <p>{ex.question}</p>
              {ex.hint && (
                <p style={{ fontSize: '0.85rem', color: '#666' }}>Hint: {ex.hint}</p>
              )}
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <input
                  placeholder="Your answer…"
                  value={answers[i] || ''}
                  onChange={(e) =>
                    setAnswers((prev) => ({ ...prev, [i]: e.target.value }))
                  }
                />
                <button
                  disabled={evaluating === i || !answers[i]?.trim() || !exerciseIds[i]}
                  onClick={() => {
                    if (exerciseIds[i]) {
                      handleEvaluate(i, exerciseIds[i]);
                    }
                  }}
                >
                  {evaluating === i ? '…' : 'Check'}
                </button>
              </div>
              {evaluations[i] && (
                <div
                  style={{
                    marginTop: '0.5rem',
                    padding: '0.5rem',
                    background: evaluations[i].is_correct ? '#d4edda' : '#f8d7da',
                    borderRadius: '6px',
                    fontSize: '0.9rem',
                  }}
                >
                  <strong>{evaluations[i].is_correct ? '✓ Correct' : '✗ Incorrect'}</strong>{' '}
                  (Score: {(evaluations[i].score * 100).toFixed(0)}%)
                  <p>{evaluations[i].feedback}</p>
                </div>
              )}
            </div>
          ))}

          {worksheet.roleplay_prompts.length > 0 && (
            <>
              <h3>Roleplay Prompts</h3>
              <ul>
                {worksheet.roleplay_prompts.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
