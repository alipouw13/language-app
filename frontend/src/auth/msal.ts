import { PublicClientApplication } from '@azure/msal-browser';
import { authConfig, loginRequest, msalConfig } from './config';

/** Module-level MSAL instance (null when auth is disabled). */
export const msalInstance = authConfig.enabled
  ? new PublicClientApplication(msalConfig)
  : null;

/** Initialise MSAL and restore an active account (call once before render). */
export async function initMsal(): Promise<void> {
  if (!msalInstance) return;
  await msalInstance.initialize();
  const result = await msalInstance.handleRedirectPromise();
  if (result?.account) {
    msalInstance.setActiveAccount(result.account);
  } else {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) msalInstance.setActiveAccount(accounts[0]);
  }
}

/**
 * Acquire an access token for the API.
 * Returns null when auth is disabled or no account is signed in.
 */
export async function acquireToken(): Promise<string | null> {
  if (!msalInstance) return null;
  const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];
  if (!account) return null;
  try {
    const res = await msalInstance.acquireTokenSilent({
      scopes: loginRequest.scopes,
      account,
    });
    return res.accessToken;
  } catch {
    // Interaction required — fall back to redirect.
    await msalInstance.acquireTokenRedirect({ scopes: loginRequest.scopes, account });
    return null;
  }
}
