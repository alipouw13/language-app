import React, { useState } from 'react';
import axios from 'axios';

const languageOptions = [
  { value: 'English', label: 'English' },
  { value: 'French', label: 'French' },
  { value: 'Spanish', label: 'Spanish' },
];

function ChatInterface() {
  const [language, setLanguage] = useState('French');
  const [input, setInput] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const newHistory = [...history, { role: 'user', content: input }];
    setHistory(newHistory);
    setInput('');
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post('http://localhost:8000/chat', {
        history: newHistory,
        language,
      });
      const reply = res.data.response;
      setHistory((prev) => [...prev, { role: 'assistant', content: reply }]);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage();
  };

  return (
    <div>
      <div style={{ marginBottom: '0.5rem' }}>
        <label>
          Chat Language:
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            {languageOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div style={{ border: '1px solid #ccc', padding: '0.5rem', height: '200px', overflowY: 'auto', marginBottom: '0.5rem' }}>
        {history.map((msg, index) => (
          <div key={index} style={{ marginBottom: '0.25rem' }}>
            <strong>{msg.role === 'user' ? 'You' : 'AI'}:</strong> {msg.content}
          </div>
        ))}
        {loading && <p>AI is typing...</p>}
      </div>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          placeholder="Say something..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={loading || !input.trim()}>Send</button>
      </form>
    </div>
  );
}

export default ChatInterface;