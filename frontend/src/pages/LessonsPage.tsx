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

type Tab = 'worksheets' | 'conversations';

export default function LessonsPage() {
  const [tab, setTab] = useState<Tab>('worksheets');

  // Worksheets
  const [lessons, setLessons] = useState<PaginatedResponse<LessonSummary> | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<LessonDetail | null>(null);
  const [lPage, setLPage] = useState(1);

  // Conversations
  const [convos, setConvos] = useState<PaginatedResponse<ConversationSummary> | null>(null);
  const [selectedConvo, setSelectedConvo] = useState<ConversationDetail | null>(null);
  const [cPage, setCPage] = useState(1);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (tab === 'worksheets') {
      loadLessons();
    } else {
      loadConversations();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, lPage, cPage]);

  const loadLessons = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listLessons(lPage);
      setLessons(data);
    } catch {
      setError('Failed to load lessons');
    } finally {
      setLoading(false);
    }
  };

  const loadConversations = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listConversations(cPage);
      setConvos(data);
    } catch {
      setError('Failed to load conversations');
    } finally {
      setLoading(false);
    }
  };

  const openLesson = async (id: string) => {
    setLoading(true);
    try {
      const data = await getLesson(id);
      setSelectedLesson(data);
    } catch {
      setError('Failed to load lesson');
    } finally {
      setLoading(false);
    }
  };

  const openConversation = async (id: string) => {
    setLoading(true);
    try {
      const data = await getConversation(id);
      setSelectedConvo(data);
    } catch {
      setError('Failed to load conversation');
    } finally {
      setLoading(false);
    }
  };

  const langBadge = (lang: string) => `badge badge-${lang}`;

  return (
    <div>
      <h2>Past Lessons Library</h2>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button
          onClick={() => { setTab('worksheets'); setSelectedLesson(null); setSelectedConvo(null); }}
          style={{ background: tab === 'worksheets' ? '#4361ee' : '#aaa' }}
        >
          Worksheets
        </button>
        <button
          onClick={() => { setTab('conversations'); setSelectedLesson(null); setSelectedConvo(null); }}
          style={{ background: tab === 'conversations' ? '#4361ee' : '#aaa' }}
        >
          Conversations
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="loading">Loading…</p>}

      {/* Worksheet detail view */}
      {selectedLesson && (
        <div className="card">
          <button onClick={() => setSelectedLesson(null)} style={{ marginBottom: '1rem', background: '#6c757d' }}>
            ← Back
          </button>
          <h3>{selectedLesson.scenario}</h3>
          <p>
            <span className={langBadge(selectedLesson.target_language)}>
              {selectedLesson.target_language.toUpperCase()}
            </span>{' '}
            Level: {selectedLesson.difficulty}
          </p>

          {selectedLesson.worksheet && (
            <>
              <h4>Grammar: {selectedLesson.worksheet.grammar_focus}</h4>
              <p>{selectedLesson.worksheet.explanations}</p>

              <h4>Vocabulary</h4>
              <table className="vocab-table">
                <thead>
                  <tr><th>Word</th><th>Translation</th><th>Example</th></tr>
                </thead>
                <tbody>
                  {selectedLesson.worksheet.vocabulary.map((v, i) => (
                    <tr key={i}>
                      <td><strong>{v.word}</strong></td>
                      <td>{v.translation}</td>
                      <td><em>{v.example_sentence}</em></td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4>Exercises</h4>
              {selectedLesson.worksheet.exercises.map((ex, i) => (
                <div key={i} className="exercise-card">
                  <span className="type-badge">{ex.type.replace('_', ' ')}</span>
                  <p><strong>Q:</strong> {ex.question}</p>
                  <p><strong>A:</strong> {ex.answer}</p>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {/* Conversation detail view */}
      {selectedConvo && (
        <div className="card">
          <button onClick={() => setSelectedConvo(null)} style={{ marginBottom: '1rem', background: '#6c757d' }}>
            ← Back
          </button>
          <h3>
            Conversation{' '}
            <span className={langBadge(selectedConvo.target_language)}>
              {selectedConvo.target_language.toUpperCase()}
            </span>
          </h3>
          {selectedConvo.scenario_context && (
            <p><em>Scenario: {selectedConvo.scenario_context}</em></p>
          )}
          <div className="chat-window" style={{ height: '400px' }}>
            {selectedConvo.turns.map((t, i) => (
              <div key={i} className={`chat-bubble ${t.role}`}>
                {t.text}
                {t.corrected_text && (
                  <p style={{ fontSize: '0.8rem', marginTop: '0.25rem', opacity: 0.8 }}>
                    Correction: {t.corrected_text}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* List views */}
      {!selectedLesson && !selectedConvo && tab === 'worksheets' && lessons && (
        <div className="card">
          {lessons.items.length === 0 ? (
            <p>No worksheets yet. Generate one from the Worksheets page!</p>
          ) : (
            lessons.items.map((l) => (
              <div key={l.id} className="lesson-list-item" onClick={() => openLesson(l.id)}>
                <div>
                  <strong>{l.scenario}</strong>
                  <br />
                  <small>{new Date(l.created_at).toLocaleDateString()} · {l.exercise_count} exercises</small>
                </div>
                <div>
                  <span className={langBadge(l.target_language)}>{l.target_language.toUpperCase()}</span>{' '}
                  <span className="badge">{l.difficulty}</span>
                </div>
              </div>
            ))
          )}
          {lessons.total > lessons.page_size && (
            <div className="pagination">
              <button disabled={lPage <= 1} onClick={() => setLPage((p) => p - 1)}>Prev</button>
              <span>Page {lPage}</span>
              <button disabled={lPage * lessons.page_size >= lessons.total} onClick={() => setLPage((p) => p + 1)}>Next</button>
            </div>
          )}
        </div>
      )}

      {!selectedLesson && !selectedConvo && tab === 'conversations' && convos && (
        <div className="card">
          {convos.items.length === 0 ? (
            <p>No conversations yet. Start one from the Conversation page!</p>
          ) : (
            convos.items.map((c) => (
              <div key={c.id} className="lesson-list-item" onClick={() => openConversation(c.id)}>
                <div>
                  <strong>{c.scenario_context || 'Free conversation'}</strong>
                  <br />
                  <small>{new Date(c.created_at).toLocaleDateString()} · {c.turn_count} turns</small>
                </div>
                <span className={langBadge(c.target_language)}>{c.target_language.toUpperCase()}</span>
              </div>
            ))
          )}
          {convos.total > convos.page_size && (
            <div className="pagination">
              <button disabled={cPage <= 1} onClick={() => setCPage((p) => p - 1)}>Prev</button>
              <span>Page {cPage}</span>
              <button disabled={cPage * convos.page_size >= convos.total} onClick={() => setCPage((p) => p + 1)}>Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
