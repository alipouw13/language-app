import React from 'react';
import TranslateForm from './components/TranslateForm';
import GrammarPractice from './components/GrammarPractice';
import ChatInterface from './components/ChatInterface';

function App() {
  return (
    <div className="App" style={{maxWidth: '800px', margin: '0 auto', fontFamily: 'sans-serif'}}>
      <h1>Language Learning App</h1>
      <p>Practice translation, grammar and conversation in English, French and Spanish.</p>
      <section>
        <h2>Translate</h2>
        <TranslateForm />
      </section>
      <hr />
      <section>
        <h2>Grammar Practice</h2>
        <GrammarPractice />
      </section>
      <hr />
      <section>
        <h2>Conversation Practice</h2>
        <ChatInterface />
      </section>
    </div>
  );
}

export default App;