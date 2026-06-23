import { useRef, useState, type ReactNode } from 'react';
import { speakWord, translateWord } from '../services/api';

/**
 * Renders text in a target language where every word is:
 *   - hover/focus → tooltip with the English (gloss) translation
 *   - click/Enter → spoken aloud via Foundry TTS for pronunciation
 *
 * Translations and audio are fetched on demand and cached (see api.ts), so
 * repeated interactions are instant and cheap. When `lang` equals the gloss
 * language, words remain clickable-to-speak but show no translation tooltip.
 */

// Split text into word vs non-word tokens, preserving punctuation/whitespace.
// Unicode-aware so accented letters (á, é, ñ, ü, ç…) stay part of the word.
const WORD_RE = /[\p{L}\p{M}][\p{L}\p{M}'’-]*/u;

interface Props {
  text: string;
  lang: string;
  gloss?: string;
  className?: string;
}

export default function InteractiveText({ text, lang, gloss = 'en', className }: Props) {
  if (!text) return null;
  const parts = splitTokens(text);
  return (
    <span className={className}>
      {parts.map((part, i) =>
        part.isWord ? (
          <Word key={i} word={part.value} lang={lang} gloss={gloss} />
        ) : (
          <span key={i}>{part.value}</span>
        ),
      )}
    </span>
  );
}

interface Token {
  value: string;
  isWord: boolean;
}

function splitTokens(text: string): Token[] {
  const tokens: Token[] = [];
  let rest = text;
  // Global, sticky-free scan using exec on a fresh regex each round is simpler
  // and avoids lastIndex pitfalls across re-renders.
  const re = new RegExp(WORD_RE, 'u');
  while (rest.length) {
    const m = re.exec(rest);
    if (!m) {
      tokens.push({ value: rest, isWord: false });
      break;
    }
    if (m.index > 0) tokens.push({ value: rest.slice(0, m.index), isWord: false });
    tokens.push({ value: m[0], isWord: true });
    rest = rest.slice(m.index + m[0].length);
  }
  return tokens;
}

function Word({ word, lang, gloss }: { word: string; lang: string; gloss: string }): ReactNode {
  const [open, setOpen] = useState(false);
  const [translation, setTranslation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const hoverTimer = useRef<number | null>(null);

  const showTip = lang !== gloss;

  const loadTranslation = () => {
    if (!showTip || translation !== null || loading) return;
    setLoading(true);
    translateWord(word, lang, gloss)
      .then((t) => setTranslation(t || '—'))
      .catch(() => setTranslation('—'))
      .finally(() => setLoading(false));
  };

  const onEnter = () => {
    if (!showTip) return;
    hoverTimer.current = window.setTimeout(() => {
      setOpen(true);
      loadTranslation();
    }, 180);
  };

  const onLeave = () => {
    if (hoverTimer.current) {
      window.clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
    setOpen(false);
  };

  const speak = () => {
    if (speaking) return;
    setSpeaking(true);
    speakWord(word, lang)
      .catch(() => undefined)
      .finally(() => setSpeaking(false));
  };

  return (
    <span
      className={`iword${speaking ? ' speaking' : ''}`}
      tabIndex={0}
      role="button"
      aria-label={`${word}. Click to hear pronunciation`}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={() => {
        if (showTip) {
          setOpen(true);
          loadTranslation();
        }
      }}
      onBlur={() => setOpen(false)}
      onClick={speak}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          speak();
        }
      }}
    >
      {word}
      {open && showTip && (
        <span className="iword-tip" role="tooltip">
          {loading ? '…' : translation}
        </span>
      )}
    </span>
  );
}
