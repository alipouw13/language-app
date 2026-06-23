export type LangCode = 'en' | 'fr' | 'es';
export type Level = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';

export const LANGUAGES: { code: LangCode; label: string }[] = [
  { code: 'fr', label: 'French' },
  { code: 'es', label: 'Spanish' },
  { code: 'en', label: 'English' },
];

export const LEVELS: Level[] = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

// Verb tenses organised by language.
export const GRAMMAR_OPTIONS: Record<LangCode, { value: string; label: string }[]> = {
  en: [
    { value: '', label: '— Any / default —' },
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
    { value: '', label: '— N’importe lequel —' },
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
    { value: '', label: '— Cualquiera —' },
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
