import { useEffect, useState } from 'react';
import type {
  ConversationDetail,
  ConversationSummary,
  LessonDetail,
  LessonSummary,
  PaginatedResponse,
} from '../types';
import {
  getConversation,
  getLesson,
  listConversations,
  listLessons,
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

type Tab = 'worksheets' | 'conversations';

export default function LessonsPage() {
  const [tab, setTab] = useState<Tab>('worksheets');
  const [lessons, setLessons] = useState<PaginatedResponse<LessonSummary> | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<LessonDetail | null>(null);
  const [lPage, setLPage] = useState(1);
  const [convos, setConvos] = useState<PaginatedResponse<ConversationSummary> | null>(null);
  const [selectedConvo, setSelectedConvo] = useState<ConversationDetail | null>(null);
  const [cPage, setCPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const load =
      tab === 'worksheets'
        ? listLessons(lPage).then((d) => active && setLessons(d))
        : listConversations(cPage).then((d) => active && setConvos(d));
    load
      .catch(() => active && setError('Failed to load history'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [tab, lPage, cPage]);

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

  const switchTab = (t: Tab) => {
    setTab(t);
    setSelectedLesson(null);
    setSelectedConvo(null);
  };

  return (
    <div className="page">
      <header className="page-head">
        <h1>History</h1>
        <p className="muted">Your saved worksheets and conversations, stored in OneLake.</p>
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
              <p className="prose">{selectedLesson.worksheet.explanations}</p>

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
                        <strong>{v.word}</strong>
                      </td>
                      <td>{v.translation}</td>
                      <td className="muted">
                        <em>{v.example_sentence}</em>
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
                    <strong>Q:</strong> {ex.question}
                  </p>
                  <p>
                    <strong>A:</strong> {ex.answer}
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
                {t.text}
                {t.corrected_text && (
                  <p className="correction">Correction: {t.corrected_text}</p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {!selectedLesson && !selectedConvo && tab === 'worksheets' && lessons && (
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

      {!selectedLesson && !selectedConvo && tab === 'conversations' && convos && (
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
    </div>
  );
}
