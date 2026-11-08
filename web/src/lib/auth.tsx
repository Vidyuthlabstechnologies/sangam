import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { AuthProvider as OidcAuthProvider, useAuth as useOidcAuth } from "react-oidc-context";
import { setAccessTokenGetter } from "./api";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
  error: string | null;
  configured: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

function oidcSettings() {
  const authority = import.meta.env.VITE_ZITADEL_ISSUER;
  const clientId = import.meta.env.VITE_ZITADEL_CLIENT_ID;
  if (!authority || !clientId) return null;
  return {
    authority,
    client_id: clientId,
    redirect_uri: `${window.location.origin}/login`,
    post_logout_redirect_uri: `${window.location.origin}/login`,
    response_type: "code" as const,
    scope: "openid profile email offline_access urn:zitadel:iam:user:resourceowner",
    automaticSilentRenew: true,
    // Public PKCE client. There is no client secret in the browser.
  };
}

const missingConfig: AuthContextType = {
  token: null,
  isAuthenticated: false,
  isLoading: false,
  configured: false,
  error: "Set VITE_ZITADEL_ISSUER and VITE_ZITADEL_CLIENT_ID to the self-hosted Zitadel instance.",
  login: async () => {},
  logout: async () => {
    localStorage.removeItem("sangam_actor_id");
  },
};

function TokenBridge({ children }: { children: ReactNode }) {
  const oidc = useOidcAuth();
  const accessToken = oidc.user?.access_token ?? null;

  useEffect(() => {
    setAccessTokenGetter(() => accessToken);
    if (!oidc.isAuthenticated || !accessToken) return;
    let cancelled = false;
    fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (!cancelled && body?.actor_id) {
          localStorage.setItem("sangam_actor_id", body.actor_id);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [oidc.isAuthenticated, accessToken]);

  const value = useMemo<AuthContextType>(
    () => ({
      token: accessToken,
      isAuthenticated: oidc.isAuthenticated,
      isLoading: oidc.isLoading,
      configured: true,
      error: oidc.error ? oidc.error.message : null,
      login: () => oidc.signinRedirect(),
      logout: async () => {
        localStorage.removeItem("sangam_actor_id");
        await oidc.signoutRedirect();
      },
    }),
    [accessToken, oidc],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const settings = oidcSettings();
  if (!settings) {
    return <AuthContext.Provider value={missingConfig}>{children}</AuthContext.Provider>;
  }
  return (
    <OidcAuthProvider
      {...settings}
      onSigninCallback={() => {
        window.history.replaceState({}, document.title, window.location.pathname);
      }}
    >
      <TokenBridge>{children}</TokenBridge>
    </OidcAuthProvider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useRequireAuth() {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate("/login", { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  return { isAuthenticated, isLoading };
}
