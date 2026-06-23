import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { Button, Card } from './components/ui';
import { useAuth } from './auth/AuthProvider';
import ScenarioPage from './pages/ScenarioPage';
import VerbPracticePage from './pages/VerbPracticePage';
import ConversationPage from './pages/ConversationPage';
import TranslatePage from './pages/TranslatePage';
import LessonsPage from './pages/LessonsPage';

function SignInGate() {
  const auth = useAuth();
  return (
    <div className="signin">
      <Card className="signin-card">
        <span className="brand-mark large" aria-hidden>
          文A
        </span>
        <h1>Lingua Foundry</h1>
        <p className="muted">
          Practice French, Spanish and English with Azure AI Foundry models. Sign in
          with your Microsoft Entra account to continue.
        </p>
        <Button onClick={auth.login}>Sign in with Microsoft</Button>
      </Card>
    </div>
  );
}

export default function App() {
  const auth = useAuth();

  if (auth.enabled && !auth.isAuthenticated) {
    return <SignInGate />;
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ScenarioPage />} />
        <Route path="/verbs" element={<VerbPracticePage />} />
        <Route path="/conversation" element={<ConversationPage />} />
        <Route path="/translate" element={<TranslatePage />} />
        <Route path="/lessons" element={<LessonsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
