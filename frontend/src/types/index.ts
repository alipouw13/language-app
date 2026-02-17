export interface VocabularyItem {
  word: string;
  translation: string;
  example_sentence: string;
}

export interface ExerciseItem {
  type: 'fill_blank' | 'conjugation' | 'sentence_building' | 'translation';
  question: string;
  answer: string;
  hint: string;
}

export interface Worksheet {
  scenario_summary: string;
  vocabulary: VocabularyItem[];
  grammar_focus: string;
  explanations: string;
  exercises: ExerciseItem[];
  roleplay_prompts: string[];
}

export interface WorksheetRequest {
  scenario: string;
  target_language: 'en' | 'fr' | 'es';
  grammar_focus?: string;
  difficulty: 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
  user_id?: string;
}

export interface LessonResponse {
  lesson_id: string;
  worksheet: Worksheet;
  exercise_ids: string[];
}

export interface ExerciseDbItem {
  id: string;
  type: string;
  question: string;
  hint: string;
  order_index: number;
}

export interface LessonDetail {
  id: string;
  target_language: string;
  scenario: string;
  grammar_focus: string | null;
  difficulty: string;
  worksheet: Worksheet;
  version: number;
  created_at: string;
  exercises: ExerciseDbItem[];
}

export interface ExerciseEvaluation {
  is_correct: boolean;
  score: number;
  feedback: string;
  correct_answer: string;
}

export interface ConversationTurn {
  role: 'user' | 'assistant';
  text: string;
  corrected_text?: string;
  turn_index: number;
}

export interface ConversationDetail {
  id: string;
  target_language: string;
  scenario_context: string | null;
  created_at: string;
  turns: ConversationTurn[];
}

export interface LessonSummary {
  id: string;
  scenario: string;
  target_language: string;
  difficulty: string;
  exercise_count: number;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  target_language: string;
  scenario_context: string | null;
  turn_count: number;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
