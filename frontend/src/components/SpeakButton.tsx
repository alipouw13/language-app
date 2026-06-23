import { useState } from 'react';
import { speakText } from '../services/api';

/**
 * A small speaker button that plays a whole sentence/phrase aloud via the
 * Foundry TTS model (cached). Reused on conversation bubbles and translations.
 */
export default function SpeakButton({
  text,
  lang,
  title = 'Hear pronunciation',
  className = '',
}: {
  text: string;
  lang: string;
  title?: string;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);

  const play = () => {
    if (busy || !text.trim()) return;
    setBusy(true);
    speakText(text, lang)
      .catch(() => undefined)
      .finally(() => setBusy(false));
  };

  return (
    <button
      type="button"
      className={`speak-btn${busy ? ' speaking' : ''} ${className}`}
      onClick={play}
      aria-label={title}
      title={title}
    >
      {busy ? '◌' : '🔊'}
    </button>
  );
}
