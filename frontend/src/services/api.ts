import axios from 'axios';
import type {
  ConversationDetail,
  ConversationSummary,
  ExerciseEvaluation,
  LessonDetail,
  LessonResponse,
  LessonSummary,
  PaginatedResponse,
  WorksheetRequest,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// --- Worksheets ---

export async function generateWorksheet(req: WorksheetRequest): Promise<LessonResponse> {
  const { data } = await api.post('/worksheets', req);
  return data;
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
