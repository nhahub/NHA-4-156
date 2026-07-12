import { createContext, useContext, useEffect, useState, useCallback } from "react";

const AuthContext = createContext(null);

// Same base as lib/api.jsx: "" for same-origin (Docker) and the Vite dev proxy.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

/**
 * App-wide auth state. On mount, calls GET /auth/me to see if the browser has
 * a valid session cookie. Exposes { user, loading, login, logout }.
 *
 * login() does a full-page redirect to /auth/login (leaves the SPA — GitHub
 * OAuth flow). After the backend sets the cookie it redirects back to "/".
 *
 * logout() POSTs /auth/logout to clear the server session, then clears local
 * state. The frontend teammate can wire this into the Navbar avatar dropdown.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, { credentials: "include" });
        if (cancelled) return;
        if (res.ok) {
          setUser(await res.json());
        } else {
          setUser(null);
        }
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(() => {
    // Full redirect — the OAuth flow leaves the SPA and comes back. Pass the
    // page we're on so the backend can return us here instead of "/".
    const next = window.location.pathname + window.location.search;
    window.location.href = `${API_BASE}/auth/login?next=${encodeURIComponent(next)}`;
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
    } catch {
      // ignore — clear local state regardless
    }
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside an <AuthProvider>");
  return ctx;
}
