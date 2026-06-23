import { useState } from 'react';
import type { ExerciseEvaluation, Worksheet } from '../types';
import { evaluateExercise } from '../services/api';
import InteractiveText from './InteractiveText';
import { Badge, Button, Card, TextInput } from './ui';

interface Props {
  worksheet: Worksheet;
  /** Language of the target-language content (for hover-translate + speak). */
  lang: string;
  exerciseIds?: string[];
}

/** Renders a generated worksheet, with inline exercise checking when ids exist. */
export default function WorksheetView({ worksheet, lang, exerciseIds = [] }: Props) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [evals, setEvals] = useState<Record<number, ExerciseEvaluation>>({});
  const [busy, setBusy] = useState<number | null>(null);

  const check = async (i: number, exerciseId: string) => {
    const answer = answers[i];
    if (!answer?.trim()) return;
    setBusy(i);
    try {
      const result = await evaluateExercise(exerciseId, answer);
      setEvals((prev) => ({ ...prev, [i]: result }));
    } catch {
      setEvals((prev) => ({
        ...prev,
        [i]: { is_correct: false, score: 0, feedback: 'Evaluation failed', correct_answer: '' },
      }));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="worksheet">
      <header className="worksheet-head">
        {worksheet.verb && <Badge>verb · {worksheet.verb}</Badge>}
        <h2>
          <InteractiveText text={worksheet.scenario_summary} lang={lang} />
        </h2>
        <p className="muted">
          <strong>Grammar focus:</strong> {worksheet.grammar_focus}
        </p>
      </header>

      <section>
        <h3>Explanation</h3>
        <p className="prose">
          <InteractiveText text={worksheet.explanations} lang={lang} />
        </p>
      </section>

      {worksheet.conjugation_table && worksheet.conjugation_table.length > 0 && (
        <section>
          <h3>Conjugation</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Pronoun</th>
                <th>Form</th>
                <th>Meaning</th>
              </tr>
            </thead>
            <tbody>
              {worksheet.conjugation_table.map((row, i) => (
                <tr key={i}>
                  <td>
                    <InteractiveText text={row.pronoun} lang={lang} />
                  </td>
                  <td>
                    <strong>
                      <InteractiveText text={row.form} lang={lang} />
                    </strong>
                  </td>
                  <td className="muted">{row.translation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h3>Vocabulary</h3>
        <table className="data-table">
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
                <td>
                  <strong>
                    <InteractiveText text={v.word} lang={lang} />
                  </strong>
                </td>
                <td>{v.translation}</td>
                <td>
                  <em className="muted">
                    <InteractiveText text={v.example_sentence} lang={lang} />
                  </em>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3>Exercises</h3>
        {worksheet.exercises.map((ex, i) => (
          <div key={i} className="exercise">
            <span className="type-badge">{ex.type.replace('_', ' ')}</span>
            <p className="exercise-q">
              <InteractiveText text={ex.question} lang={lang} />
            </p>
            {ex.hint && <p className="field-hint">Hint: {ex.hint}</p>}
            <div className="exercise-answer">
              <TextInput
                placeholder="Your answer…"
                value={answers[i] ?? ''}
                onChange={(e) => setAnswers((p) => ({ ...p, [i]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && exerciseIds[i]) check(i, exerciseIds[i]);
                }}
              />
              <Button
                variant="secondary"
                disabled={busy === i || !answers[i]?.trim() || !exerciseIds[i]}
                onClick={() => exerciseIds[i] && check(i, exerciseIds[i])}
              >
                {busy === i ? '…' : 'Check'}
              </Button>
            </div>
            {evals[i] && (
              <div className={`result ${evals[i].is_correct ? 'ok' : 'bad'}`}>
                <strong>{evals[i].is_correct ? '✓ Correct' : '✗ Not quite'}</strong>{' '}
                <span className="muted">({Math.round(evals[i].score * 100)}%)</span>
                <p>{evals[i].feedback}</p>
              </div>
            )}
          </div>
        ))}
      </section>

      {worksheet.roleplay_prompts.length > 0 && (
        <section>
          <h3>Roleplay prompts</h3>
          <ul className="prompt-list">
            {worksheet.roleplay_prompts.map((p, i) => (
              <li key={i}>
                <InteractiveText text={p} lang={lang} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </Card>
  );
}
