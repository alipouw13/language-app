import React, { useState } from 'react';
import axios from 'axios';

const options = [
  { value: 'English', label: 'English' },
  { value: 'French', label: 'French' },
  { value: 'Spanish', label: 'Spanish' },
];

function GrammarPractice() {
  const [sentence, setSentence] = useState('');
  const [language, setLanguage] = useState('French');
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await axios.post('http://localhost:8000/grammar', {
        sentence,
        language,
      });
      setFeedback(res.data.feedback);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        <textarea
          rows="3"
          placeholder="Type a sentence to check grammar"
          value={sentence}
          onChange={(e) => setSentence(e.target.value)}
        />
        <label>
          Language:
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={loading || !sentence}>Check Grammar</button>
      </form>
      {loading && <p>Checking grammar...</p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {feedback && (
        <div style={{ marginTop: '1rem' }}>
          <h3>Feedback:</h3>
          <p>{feedback}</p>
        </div>
      )}
    </div>
  );
}

export default GrammarPractice;