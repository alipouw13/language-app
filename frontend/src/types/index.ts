export interface VocabularyItem {
  word: string;
  translation: string;
  example_sentence: string;
}

export interface ConjugationRow {
  pronoun: string;
  form: string;
  translation: string;
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
  verb?: string | null;
  conjugation_table?: ConjugationRow[];
}

export interface WorksheetRequest {
  scenario: string;
  target_language: 'en' | 'fr' | 'es';
  grammar_focus?: string;
  difficulty: 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
}

export interface VerbWorksheetRequest {
  verb: string;
  target_language: 'en' | 'fr' | 'es';
  native_language: 'en' | 'fr' | 'es';
  grammar_focus?: string;
  difficulty: 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
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
  mode?: string;
  verb?: string | null;
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

export interface WorksheetResponseItem {
  exercise_id: string;
  order_index: number;
  exercise_type: string;
  question: string;
  user_answer: string;
  first_score: number | null;
  first_is_correct: boolean | null;
  final_score: number | null;
  final_is_correct: boolean | null;
  attempts: number;
  feedback: string | null;
}

export interface WorksheetSubmissionResult {
  submission_id: string;
  lesson_id: string;
  total_exercises: number;
  answered_count: number;
  first_score_avg: number;
  final_score_avg: number;
  first_correct_count: number;
  final_correct_count: number;
  submitted_at: string;
}

export interface SubmissionSummary {
  submission_id: string;
  lesson_id: string;
  target_language: string;
  mode: string;
  verb: string | null;
  scenario: string | null;
  difficulty: string;
  grammar_focus: string | null;
  total_exercises: number;
  answered_count: number;
  first_correct_count: number;
  final_correct_count: number;
  first_score_avg: number;
  final_score_avg: number;
  submitted_at: string;
  date_key: number;
}

export interface SubmissionResponseRow {
  response_id: string;
  exercise_id: string;
  order_index: number;
  exercise_type: string;
  question: string;
  correct_answer: string;
  user_answer: string;
  first_score: number | null;
  first_is_correct: boolean | null;
  final_score: number | null;
  final_is_correct: boolean | null;
  attempts: number;
  feedback: string | null;
}

export interface SubmissionDetail extends SubmissionSummary {
  responses: SubmissionResponseRow[];
}

export interface VerbOption {
  verb: string;
  gloss: string;
}

export interface TranslationResult {
  source_language: string;
  translations: Record<string, string>;
  model: string;
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
  mode?: string;
  verb?: string | null;
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
