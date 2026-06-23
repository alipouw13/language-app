import { useEffect, useState } from 'react';
import type {
  ConversationDetail,
  ConversationSummary,
  LessonDetail,
  LessonSummary,
  PaginatedResponse,
  SubmissionDetail,
  SubmissionSummary,
} from '../types';
import {
  getConversation,
  getLesson,
  getSubmission,
  listConversations,
  listLessons,
  listSubmissions,
} from '../services/api';
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  LanguageBadge,
  Spinner,
} from '../components/ui';
import InteractiveText from '../components/InteractiveText';

type Tab = 'worksheets' | 'conversations' | 'progress';

const pct = (n: number) => `${Math.round((n ?? 0) * 100)}%`;

export default function LessonsPage() {
  const [tab, setTab] = useState<Tab>('worksheets');
  const [lessons, setLessons] = useState<PaginatedResponse<LessonSummary> | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<LessonDetail | null>(null);
  const [lPage, setLPage] = useState(1);
  const [convos, setConvos] = useState<PaginatedResponse<ConversationSummary> | null>(null);
  const [selectedConvo, setSelectedConvo] = useState<ConversationDetail | null>(null);
  const [cPage, setCPage] = useState(1);
  const [subs, setSubs] = useState<PaginatedResponse<SubmissionSummary> | null>(null);
  const [selectedSub, setSelectedSub] = useState<SubmissionDetail | null>(null);
  const [sPage, setSPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    let load: Promise<unknown>;
    if (tab === 'worksheets') {
      load = listLessons(lPage).then((d) => active && setLessons(d));
    } else if (tab === 'conversations') {
      load = listConversations(cPage).then((d) => active && setConvos(d));
    } else {
      load = listSubmissions(sPage).then((d) => active && setSubs(d));
    }
    load
      .catch(() => active && setError('Failed to load history'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [tab, lPage, cPage, sPage]);

  const openLesson = async (id: string) => {
    setLoading(true);
    try {
      setSelectedLesson(await getLesson(id));
    } catch {
      setError('Failed to load lesson');
    } finally {
      setLoading(false);
    }
  };

  const openConversation = async (id: string) => {
    setLoading(true);
    try {
      setSelectedConvo(await getConversation(id));
    } catch {
      setError('Failed to load conversation');
    } finally {
      setLoading(false);
    }
  };

  const openSubmission = async (id: string) => {
    setLoading(true);
    try {
      setSelectedSub(await getSubmission(id));
    } catch {
      setError('Failed to load submission');
    } finally {
      setLoading(false);
    }
  };

  const switchTab = (t: Tab) => {
    setTab(t);
    setSelectedLesson(null);
    setSelectedConvo(null);
    setSelectedSub(null);
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>History</h1>
        <p className="muted">
          Your saved worksheets, conversations and submitted progress — stored in OneLake.
        </p>
      </header>

      <div className="segmented" role="tablist">
        <button
          role="tab"
          aria-selected={tab === 'worksheets'}
          className={tab === 'worksheets' ? 'seg active' : 'seg'}
          onClick={() => switchTab('worksheets')}
        >
          Worksheets
        </button>
        <button
          role="tab"
          aria-selected={tab === 'conversations'}
          className={tab === 'conversations' ? 'seg active' : 'seg'}
          onClick={() => switchTab('conversations')}
        >
          Conversations
        </button>
        <button
          role="tab"
          aria-selected={tab === 'progress'}
          className={tab === 'progress' ? 'seg active' : 'seg'}
          onClick={() => switchTab('progress')}
        >
          Progress
        </button>
      </div>

      {error && <Alert>{error}</Alert>}
      {loading && <Spinner label="Loading…" />}

      {selectedLesson && (
        <Card>
          <Button variant="ghost" onClick={() => setSelectedLesson(null)}>
            ← Back
          </Button>
          <h2>{selectedLesson.scenario}</h2>
          <p>
            <LanguageBadge code={selectedLesson.target_language} />{' '}
            <Badge>{selectedLesson.difficulty}</Badge>{' '}
            {selectedLesson.verb && <Badge>verb · {selectedLesson.verb}</Badge>}
          </p>
          {selectedLesson.worksheet && (
            <>
              <h3>Grammar: {selectedLesson.worksheet.grammar_focus}</h3>
              <p className="prose">
                <InteractiveText
                  text={selectedLesson.worksheet.explanations}
                  lang={selectedLesson.target_language}
                />
              </p>

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
                  {selectedLesson.worksheet.vocabulary.map((v, i) => (
                    <tr key={i}>
                      <td>
                        <strong>
                          <InteractiveText text={v.word} lang={selectedLesson.target_language} />
                        </strong>
                      </td>
                      <td>{v.translation}</td>
                      <td className="muted">
                        <em>
                          <InteractiveText
                            text={v.example_sentence}
                            lang={selectedLesson.target_language}
                          />
                        </em>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h3>Exercises</h3>
              {selectedLesson.worksheet.exercises.map((ex, i) => (
                <div key={i} className="exercise">
                  <span className="type-badge">{ex.type.replace('_', ' ')}</span>
                  <p>
                    <strong>Q:</strong>{' '}
                    <InteractiveText text={ex.question} lang={selectedLesson.target_language} />
                  </p>
                  <p>
                    <strong>A:</strong>{' '}
                    <InteractiveText text={ex.answer} lang={selectedLesson.target_language} />
                  </p>
                </div>
              ))}
            </>
          )}
        </Card>
      )}

      {selectedConvo && (
        <Card>
          <Button variant="ghost" onClick={() => setSelectedConvo(null)}>
            ← Back
          </Button>
          <h2>
            Conversation <LanguageBadge code={selectedConvo.target_language} />
          </h2>
          {selectedConvo.scenario_context && (
            <p className="muted">
              <em>Scenario: {selectedConvo.scenario_context}</em>
            </p>
          )}
          <div className="chat-window tall">
            {selectedConvo.turns.map((t, i) => (
              <div key={i} className={`bubble ${t.role}`}>
                <InteractiveText text={t.text} lang={selectedConvo.target_language} />
                {t.corrected_text && (
                  <p className="correction">Correction: {t.corrected_text}</p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {selectedSub && (
        <Card>
          <Button variant="ghost" onClick={() => setSelectedSub(null)}>
            ← Back
          </Button>
          <h2>
            {selectedSub.mode === 'verb' && selectedSub.verb
              ? `Verb practice · ${selectedSub.verb}`
              : selectedSub.scenario || 'Worksheet'}{' '}
            <LanguageBadge code={selectedSub.target_language} />
          </h2>
          <p className="muted">
            Submitted {new Date(selectedSub.submitted_at).toLocaleString()} ·{' '}
            {selectedSub.answered_count}/{selectedSub.total_exercises} answered
          </p>

          <div className="score-cards">
            <div className="score-card">
              <span className="score-label">First score</span>
              <span className="score-value">{pct(selectedSub.first_score_avg)}</span>
            </div>
            <div className="score-card">
              <span className="score-label">Corrected score</span>
              <span className="score-value good">{pct(selectedSub.final_score_avg)}</span>
            </div>
            <div className="score-card">
              <span className="score-label">Improvement</span>
              <span className="score-value">
                +{pct(selectedSub.final_score_avg - selectedSub.first_score_avg)}
              </span>
            </div>
          </div>

          <h3>Responses</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Question</th>
                <th>Your answer</th>
                <th>Correct</th>
                <th>First</th>
                <th>Final</th>
                <th>Tries</th>
              </tr>
            </thead>
            <tbody>
              {selectedSub.responses.map((r) => (
                <tr key={r.response_id}>
                  <td>{r.order_index + 1}</td>
                  <td>
                    <InteractiveText text={r.question} lang={selectedSub.target_language} />
                  </td>
                  <td>{r.user_answer || <span className="muted">—</span>}</td>
                  <td>
                    <InteractiveText
                      text={r.correct_answer}
                      lang={selectedSub.target_language}
                    />
                  </td>
                  <td>{r.first_score === null ? '—' : pct(r.first_score)}</td>
                  <td className={r.final_is_correct ? 'cell-good' : undefined}>
                    {r.final_score === null ? '—' : pct(r.final_score)}
                  </td>
                  <td>{r.attempts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {!selectedLesson && !selectedConvo && !selectedSub && tab === 'worksheets' && lessons && (
        <Card>
          {lessons.items.length === 0 ? (
            <EmptyState>No worksheets yet — generate one to get started.</EmptyState>
          ) : (
            lessons.items.map((l) => (
              <div key={l.id} className="list-item" onClick={() => openLesson(l.id)}>
                <div>
                  <strong>{l.scenario}</strong>
                  <br />
                  <small className="muted">
                    {new Date(l.created_at).toLocaleDateString()} · {l.exercise_count} exercises
                  </small>
                </div>
                <div className="list-meta">
                  <LanguageBadge code={l.target_language} />
                  <Badge>{l.difficulty}</Badge>
                </div>
              </div>
            ))
          )}
          {lessons.total > lessons.page_size && (
            <div className="pagination">
              <Button variant="secondary" disabled={lPage <= 1} onClick={() => setLPage((p) => p - 1)}>
                Prev
              </Button>
              <span>Page {lPage}</span>
              <Button
                variant="secondary"
                disabled={lPage * lessons.page_size >= lessons.total}
                onClick={() => setLPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </Card>
      )}

      {!selectedLesson && !selectedConvo && !selectedSub && tab === 'conversations' && convos && (
        <Card>
          {convos.items.length === 0 ? (
            <EmptyState>No conversations yet — start one to see it here.</EmptyState>
          ) : (
            convos.items.map((c) => (
              <div key={c.id} className="list-item" onClick={() => openConversation(c.id)}>
                <div>
                  <strong>{c.scenario_context || 'Free conversation'}</strong>
                  <br />
                  <small className="muted">
                    {new Date(c.created_at).toLocaleDateString()} · {c.turn_count} turns
                  </small>
                </div>
                <LanguageBadge code={c.target_language} />
              </div>
            ))
          )}
          {convos.total > convos.page_size && (
            <div className="pagination">
              <Button variant="secondary" disabled={cPage <= 1} onClick={() => setCPage((p) => p - 1)}>
                Prev
              </Button>
              <span>Page {cPage}</span>
              <Button
                variant="secondary"
                disabled={cPage * convos.page_size >= convos.total}
                onClick={() => setCPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </Card>
      )}

      {!selectedSub && tab === 'progress' && subs && (
        <Card>
          {subs.items.length === 0 ? (
            <EmptyState>
              No submissions yet — finish a worksheet and click <strong>Submit worksheet</strong>.
            </EmptyState>
          ) : (
            subs.items.map((s) => (
              <div
                key={s.submission_id}
                className="list-item"
                onClick={() => openSubmission(s.submission_id)}
              >
                <div>
                  <strong>
                    {s.mode === 'verb' && s.verb
                      ? `Verb · ${s.verb}`
                      : s.scenario || 'Worksheet'}
                  </strong>
                  <br />
                  <small className="muted">
                    {new Date(s.submitted_at).toLocaleDateString()} ·{' '}
                    {s.answered_count}/{s.total_exercises} answered · first {pct(s.first_score_avg)} →{' '}
                    corrected {pct(s.final_score_avg)}
                  </small>
                </div>
                <div className="list-meta">
                  <LanguageBadge code={s.target_language} />
                  <Badge>{s.difficulty}</Badge>
                </div>
              </div>
            ))
          )}
          {subs.total > subs.page_size && (
            <div className="pagination">
              <Button variant="secondary" disabled={sPage <= 1} onClick={() => setSPage((p) => p - 1)}>
                Prev
              </Button>
              <span>Page {sPage}</span>
              <Button
                variant="secondary"
                disabled={sPage * subs.page_size >= subs.total}
                onClick={() => setSPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
