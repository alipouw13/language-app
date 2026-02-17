import { Routes, Route, NavLink } from 'react-router-dom';
import ScenarioPage from './pages/ScenarioPage';
import ConversationPage from './pages/ConversationPage';
import LessonsPage from './pages/LessonsPage';

function App() {
  return (
    <div className="app">
      <h1>Language Learning App</h1>
      <nav>
        <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : '')}>
          Worksheets
        </NavLink>
        <NavLink
          to="/conversation"
          className={({ isActive }) => (isActive ? 'active' : '')}
        >
          Conversation
        </NavLink>
        <NavLink to="/lessons" className={({ isActive }) => (isActive ? 'active' : '')}>
          Past Lessons
        </NavLink>
      </nav>

      <Routes>
        <Route path="/" element={<ScenarioPage />} />
        <Route path="/conversation" element={<ConversationPage />} />
        <Route path="/lessons" element={<LessonsPage />} />
      </Routes>
    </div>
  );
}

export default App;
