import axios from 'axios';
import { acquireToken } from '../auth/msal';
import type {
  ConversationDetail,
  ConversationSummary,
  ExerciseEvaluation,
  LessonDetail,
  LessonResponse,
  LessonSummary,
  PaginatedResponse,
  TranslationResult,
  VerbOption,
  VerbWorksheetRequest,
  WorksheetRequest,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Attach the Entra bearer token to every request (no-op when auth disabled).
api.interceptors.request.use(async (config) => {
  const token = await acquireToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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
): Promise<{ id: string; target_language: string; scenario_context: string | null }> {
  const { data } = await api.post('/conversations', {
    target_language: targetLanguage,
    scenario_context: scenarioContext,
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
