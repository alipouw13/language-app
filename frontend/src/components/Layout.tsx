import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { Button } from './ui';

const NAV = [
  { to: '/', label: 'Worksheets', end: true },
  { to: '/verbs', label: 'Verb Practice' },
  { to: '/conversation', label: 'Conversation' },
  { to: '/translate', label: 'Translate' },
  { to: '/lessons', label: 'History' },
];

export default function Layout({ children }: { children: ReactNode }) {
  const auth = useAuth();

  return (
    <div className="shell">
      <header className="appbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            文A
          </span>
          <div className="brand-text">
            <strong>Lingua Foundry</strong>
            <span className="brand-sub">Azure AI Foundry · Fabric OneLake</span>
          </div>
        </div>

        <nav className="mainnav" aria-label="Primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'navlink active' : 'navlink')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="user">
          {auth.enabled ? (
            auth.isAuthenticated ? (
              <>
                <span className="user-name" title={auth.username ?? ''}>
                  {auth.accountName ?? auth.username}
                </span>
                <Button variant="ghost" onClick={auth.logout}>
                  Sign out
                </Button>
              </>
            ) : (
              <Button onClick={auth.login}>Sign in</Button>
            )
          ) : (
            <span className="dev-pill" title="Entra auth disabled for local dev">
              Dev mode
            </span>
          )}
        </div>
      </header>

      <main className="content">{children}</main>

      <footer className="appfoot">
        Built to showcase Azure AI Foundry translation, speech &amp; chat models with
        data stored in Microsoft Fabric OneLake.
      </footer>
    </div>
  );
}
