import { createContext, useContext, type ReactNode } from 'react';
import { MsalProvider, useIsAuthenticated, useMsal } from '@azure/msal-react';
import { authConfig, loginRequest } from './config';
import { msalInstance } from './msal';

interface AuthState {
  enabled: boolean;
  isAuthenticated: boolean;
  accountName: string | null;
  username: string | null;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  enabled: false,
  isAuthenticated: true,
  accountName: 'Local Developer',
  username: 'dev@localhost',
  login: () => {},
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

function MsalAuthState({ children }: { children: ReactNode }) {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const account = accounts[0];

  const value: AuthState = {
    enabled: true,
    isAuthenticated,
    accountName: account?.name ?? null,
    username: account?.username ?? null,
    login: () => void instance.loginRedirect(loginRequest),
    logout: () => void instance.logoutRedirect(),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Wraps the app, providing auth state in both enabled and disabled modes. */
export function AuthProvider({ children }: { children: ReactNode }) {
  if (!authConfig.enabled || !msalInstance) {
    return <>{children}</>;
  }
  return (
    <MsalProvider instance={msalInstance}>
      <MsalAuthState>{children}</MsalAuthState>
    </MsalProvider>
  );
}
