import axios from 'axios';
import { acquireToken } from '../auth/msal';
import type {
  ConversationDetail,
  ConversationSummary,
  ExerciseEvaluation,
  LessonDetail,
  LessonResponse,
  LessonSummary,
  NewsTopic,
  NewsTopicsResponse,
  PaginatedResponse,
  SubmissionDetail,
  SubmissionSummary,
  TranslationResult,
  VerbOption,
  VerbWorksheetRequest,
  WorksheetRequest,
  WorksheetResponseItem,
  WorksheetSubmissionResult,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  // Long enough for the slowest legitimate LLM call (worksheet generation),
  // but bounded so a hung/unreachable backend fails fast with a clear message.
  timeout: 120000,
});

// Attach the Entra bearer token to every request (no-op when auth disabled).
api.interceptors.request.use(async (config) => {
  const token = await acquireToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Turn low-level axios failures into actionable messages. A missing response
// means we never reached the API (backend down, proxy error, or timeout).
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response) {
      const detail = error.response.data?.detail;
      if (typeof detail === 'string' && detail) {
        error.message = detail;
      }
    } else if (error?.code === 'ECONNABORTED') {
      error.message = 'The request timed out. The server is taking too long — please try again.';
    } else if (error?.request) {
      error.message = 'Cannot reach the server. Make sure the backend API is running, then retry.';
    }
    return Promise.reject(error);
  },
);

/** Authorization header for raw fetch() calls (e.g. multipart upload). */
export async function authHeader(): Promise<Record<string, string>> {
  const token = await acquireToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// --- Worksheets ---

export async function generateWorksheet(req: WorksheetRequest): Promise<LessonResponse> {
  const { data } = await api.post('/worksheets', req);
  return data;
}

export async function generateVerbWorksheet(
  req: VerbWorksheetRequest,
): Promise<LessonResponse> {
  const { data } = await api.post('/worksheets/verb', req);
  return data;
}

// --- Interactive words: hover-to-translate + click-to-speak (cached) ---

const _wordTranslationCache = new Map<string, Promise<string>>();
const _wordAudioCache = new Map<string, Promise<string>>();

/** Translate a single word/phrase into the gloss language (default English). */
export function translateWord(
  word: string,
  lang: string,
  gloss = 'en',
): Promise<string> {
  const clean = word.trim();
  if (!clean || lang === gloss) return Promise.resolve('');
  const key = `${lang}->${gloss}:${clean.toLowerCase()}`;
  let p = _wordTranslationCache.get(key);
  if (!p) {
    p = translateText(clean, [gloss], lang)
      .then((r) => r.translations[gloss] || '')
      .catch((e) => {
        _wordTranslationCache.delete(key);
        throw e;
      });
    _wordTranslationCache.set(key, p);
  }
  return p;
}

/** Speak a word/phrase aloud in the given language (cached audio). */
export async function speakWord(word: string, lang: string): Promise<void> {
  const clean = word.trim();
  if (!clean) return;
  const key = `${lang}:${clean.toLowerCase()}`;
  let p = _wordAudioCache.get(key);
  if (!p) {
    p = api
      .post('/speech/tts', { text: clean, language: lang }, { responseType: 'blob' })
      .then((res) => URL.createObjectURL(res.data as Blob))
      .catch((e) => {
        _wordAudioCache.delete(key);
        throw e;
      });
    _wordAudioCache.set(key, p);
  }
  const url = await p;
  await new Audio(url).play();
}

/** Speak a whole sentence/phrase aloud (alias of speakWord; backend caps length). */
export const speakText = speakWord;

export async function listVerbs(language: string): Promise<VerbOption[]> {
  const { data } = await api.get('/worksheets/verbs', { params: { language } });
  return data.verbs;
}

export async function getLesson(lessonId: string): Promise<LessonDetail> {
  const { data } = await api.get(`/worksheets/${lessonId}`);
  return data;
}

export async function evaluateExercise(
  exerciseId: string,
  userAnswer: string,
): Promise<ExerciseEvaluation> {
  const { data } = await api.post('/worksheets/evaluate', {
    exercise_id: exerciseId,
    user_answer: userAnswer,
  });
  return data;
}

export async function submitWorksheet(
  lessonId: string,
  responses: WorksheetResponseItem[],
): Promise<WorksheetSubmissionResult> {
  const { data } = await api.post('/worksheets/submit', {
    lesson_id: lessonId,
    responses,
  });
  return data;
}

// --- Translation (Foundry translation model) ---

export async function translateText(
  text: string,
  targetLanguages: string[],
  sourceLanguage = 'auto',
): Promise<TranslationResult> {
  const { data } = await api.post('/translate', {
    text,
    source_language: sourceLanguage,
    target_languages: targetLanguages,
  });
  return data;
}

// --- Conversations ---

export async function startConversation(
  targetLanguage: string,
  scenarioContext?: string,
  newsId?: string,
): Promise<{ id: string; target_language: string; scenario_context: string | null }> {
  const { data } = await api.post('/conversations', {
    target_language: targetLanguage,
    scenario_context: scenarioContext,
    news_id: newsId,
  });
  return data;
}

export async function sendMessage(
  conversationId: string,
  text: string,
): Promise<{ reply: string; correction: string | null }> {
  const { data } = await api.post(`/conversations/${conversationId}/message`, { text });
  return data;
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  const { data } = await api.get(`/conversations/${conversationId}`);
  return data;
}

// --- Current events (Real-Time Intelligence news) ---

export async function getNewsTopics(
  lang: string,
  level?: string,
  personalized = false,
  limit = 12,
): Promise<NewsTopicsResponse> {
  const { data } = await api.get('/news/topics', {
    params: { lang, level, personalized, limit },
  });
  return data;
}

export async function getNewsTopic(newsId: string): Promise<NewsTopic> {
  const { data } = await api.get(`/news/${newsId}`);
  return data;
}

// --- Lessons library ---

export async function listLessons(
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<LessonSummary>> {
  const { data } = await api.get('/lessons', { params: { page, page_size: pageSize } });
  return data;
}

export async function listConversations(
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<ConversationSummary>> {
  const { data } = await api.get('/lessons/conversations', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function listSubmissions(
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<SubmissionSummary>> {
  const { data } = await api.get('/lessons/submissions', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function getSubmission(submissionId: string): Promise<SubmissionDetail> {
  const { data } = await api.get(`/lessons/submissions/${submissionId}`);
  return data;
}

/**
 * Export one or more saved worksheets as a single downloadable document and
 * trigger a browser download. `format` is 'html' (printable, default) or 'md'.
 */
export async function exportLessons(
  lessonIds: string[],
  format: 'html' | 'md' = 'html',
): Promise<void> {
  const res = await api.post(
    '/lessons/export',
    { lesson_ids: lessonIds, format },
    { responseType: 'blob' },
  );

  // Prefer the server-provided filename from Content-Disposition.
  const disposition = (res.headers?.['content-disposition'] as string) || '';
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  const fallback = `language-worksheets.${format}`;
  const filename = match ? decodeURIComponent(match[1]) : fallback;

  const url = URL.createObjectURL(res.data as Blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
