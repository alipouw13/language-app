import type { Configuration, RedirectRequest } from '@azure/msal-browser';

/**
 * Microsoft Entra ID configuration, driven by Vite env vars.
 *
 * When `VITE_AUTH_ENABLED` is not "true", the app runs unauthenticated
 * (local development) — fully wired but with sign-in bypassed.
 */
export const authConfig = {
  enabled: import.meta.env.VITE_AUTH_ENABLED === 'true',
  clientId: import.meta.env.VITE_ENTRA_CLIENT_ID ?? '',
  tenantId: import.meta.env.VITE_ENTRA_TENANT_ID ?? '',
  apiScope: import.meta.env.VITE_ENTRA_API_SCOPE ?? '',
};

export const msalConfig: Configuration = {
  auth: {
    clientId: authConfig.clientId,
    authority: `https://login.microsoftonline.com/${authConfig.tenantId}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
};

export const loginRequest: RedirectRequest = {
  scopes: authConfig.apiScope ? [authConfig.apiScope] : ['User.Read'],
};
