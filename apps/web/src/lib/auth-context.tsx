/**
 * Auth Context — Enterprise JWT implementation
 *
 * Access token lives ONLY in React state (memory).
 * Refresh token is HttpOnly cookie — never touched by JS.
 * No localStorage token usage.
 * Multi-tab sync via BroadcastChannel('auth').
 */

'use client';

import React, { createContext, useContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { setTokenProvider, setRefreshHandler } from '@/lib/api/api-client';

// Role constants - MUST match backend RoleChoices exactly (lowercase)
export const ROLES = {
  ADMIN: 'admin',
  PRACTITIONER: 'practitioner',
  RECEPTION: 'reception',
  MARKETING: 'marketing',
  ACCOUNTING: 'accounting',
  RECEPTIONIST: 'reception',
  ASSISTANT: 'assistant',
} as const;

export type Role = typeof ROLES[keyof typeof ROLES];

interface BackendUser {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  roles: string[];
  is_active: boolean;
  is_superuser?: boolean;
  must_change_password?: boolean;
  practitioner_data?: {
    id: string;
    display_name: string;
    role_type: string;
    specialty: string;
    is_active: boolean;
  } | null;
}

export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  roles: string[];
  role: Role;
  is_superuser?: boolean;
  must_change_password?: boolean;
  practitioner_data?: {
    id: string;
    display_name: string;
    role_type: string;
    specialty: string;
    is_active: boolean;
  } | null;
}

interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  /** True while the initial silent token refresh is in-flight on mount.
   * AppLayout must not redirect to /login while this is true. */
  isInitializing: boolean;
  /** True when a refresh attempt definitively failed (cookie expired/invalid).
   * AppLayout uses this to distinguish "not yet checked" from "truly unauthenticated". */
  authError: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  refreshAccessToken: () => Promise<boolean>;
  hasRole: (role: Role) => boolean;
  hasAnyRole: (roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function transformUser(backendUser: BackendUser): User {
  return {
    id: backendUser.id,
    email: backendUser.email,
    first_name: backendUser.first_name,
    last_name: backendUser.last_name,
    roles: backendUser.roles,
    role: (backendUser.roles[0] || 'reception') as Role,
    is_superuser: backendUser.is_superuser || false,
    must_change_password: backendUser.must_change_password || false,
    practitioner_data: backendUser.practitioner_data,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  // True until the first silent refresh attempt finishes (success OR failure).
  // Prevents AppLayout from redirecting to /login during the async init window.
  const [isInitializing, setIsInitializing] = useState(true);
  // True when the refresh attempt definitively failed. AppLayout uses this
  // to distinguish "init not done yet" from "truly unauthenticated".
  const [authError, setAuthError] = useState(false);
  // Ref so the closure inside setTokenProvider always has the latest token
  const accessTokenRef = useRef<string | null>(null);
  // BroadcastChannel for multi-tab sync (null on SSR)
  const authChannelRef = useRef<BroadcastChannel | null>(null);
  const router = useRouter();

  // Keep ref in sync with state
  useEffect(() => {
    accessTokenRef.current = accessToken;
  }, [accessToken]);

  /**
   * Clears local auth state. Does NOT navigate — navigation is handled
   * exclusively by AppLayout based on (user === null && authError === true).
   * broadcast=false when the logout was triggered by another tab to prevent loops.
   */
  const performLocalLogout = useCallback((broadcast = true) => {
    setAccessToken(null);
    accessTokenRef.current = null;
    setUser(null);
    setIsAuthenticated(false);
    setAuthError(true);

    if (broadcast && authChannelRef.current) {
      authChannelRef.current.postMessage({ type: 'LOGOUT' });
    }
  }, []);

  const logout = useCallback(() => {
    // Best-effort: tell backend to blacklist the refresh cookie
    fetch(`${API_BASE_URL}/api/auth/logout/`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => { /* ignore network errors on logout */ });

    performLocalLogout(true);

    // Explicit user logout → navigate to login.
    // This is the ONLY place in the entire auth system that navigates.
    const pathLocale = typeof window !== 'undefined'
      ? (window.location.pathname.split('/')[1] || 'en')
      : 'en';
    router.push(`/${pathLocale}/login`);
  }, [performLocalLogout, router]);

  const refreshAccessToken = useCallback(async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/token/refresh/`, {
        method: 'POST',
        credentials: 'include', // sends the HttpOnly refresh_token cookie
      });

      if (!response.ok) {
        performLocalLogout(true);
        return false;
      }

      const data = await response.json();
      const newToken: string = data.access;
      setAccessToken(newToken);
      accessTokenRef.current = newToken;
      return true;
    } catch {
      performLocalLogout(true);
      return false;
    }
  }, [performLocalLogout]);

  const fetchAndSetUser = useCallback(async (token: string): Promise<void> => {
    const userResponse = await fetch(`${API_BASE_URL}/api/auth/me/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!userResponse.ok) {
      throw new Error('Failed to fetch user profile');
    }
    const backendUser: BackendUser = await userResponse.json();
    setUser(transformUser(backendUser));
    setIsAuthenticated(true);
  }, []);

  // Initialize BroadcastChannel and silent refresh on mount
  useEffect(() => {
    // SSR guard — BroadcastChannel is browser-only
    if (typeof window !== 'undefined') {
      const channel = new BroadcastChannel('auth');
      authChannelRef.current = channel;

      channel.onmessage = (event: MessageEvent) => {
        if (!event?.data?.type) return;

        if (event.data.type === 'LOGOUT') {
          performLocalLogout(false); // do not rebroadcast
        }

        if (event.data.type === 'LOGIN') {
          refreshAccessToken();
        }
      };
    }

    // Silent refresh via HttpOnly cookie.
    // setIsInitializing(false) MUST always run, regardless of outcome,
    // so AppLayout never gets stuck in the loading state.
    (async () => {
      try {
        const ok = await refreshAccessToken();
        if (ok && accessTokenRef.current) {
          try {
            await fetchAndSetUser(accessTokenRef.current);
          } catch {
            performLocalLogout(true);
          }
        }
      } finally {
        setIsInitializing(false);
      }
    })();

    return () => {
      authChannelRef.current?.close();
      authChannelRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Wire ApiClient: always return latest in-memory token
  useEffect(() => {
    setTokenProvider(() => accessTokenRef.current);
    setRefreshHandler(refreshAccessToken);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (email: string, password: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/api/auth/token/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // backend sets refresh_token cookie here
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      let errorMessage = 'Login failed';
      try {
        const contentType = response.headers.get('content-type');
        if (contentType?.includes('application/json')) {
          const error = await response.json();
          errorMessage = error.detail || errorMessage;
        }
      } catch { /* ignore */ }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    // Access token → memory only. Refresh token is in HttpOnly cookie (set by backend).
    const token: string = data.access;
    setAccessToken(token);
    accessTokenRef.current = token;
    setAuthError(false);

    await fetchAndSetUser(token);

    // Notify other tabs to reconstruct their session via the HttpOnly cookie
    authChannelRef.current?.postMessage({ type: 'LOGIN' });
  };

  const refreshUser = async (): Promise<void> => {
    if (!accessTokenRef.current) {
      throw new Error('No access token in memory');
    }
    await fetchAndSetUser(accessTokenRef.current);
  };

  const hasRole = (role: Role): boolean => {
    if (!user) return false;
    const roleNormalized = role.toLowerCase();
    const userRoles = user.roles?.map((r: string) => r.toLowerCase()) || [];
    return userRoles.includes(roleNormalized) || user.role?.toLowerCase() === roleNormalized;
  };

  const hasAnyRole = (roles: Role[]): boolean => {
    if (!user) return false;
    const rolesNormalized = roles.map((r: string) => r.toLowerCase());
    const userRoles = user.roles?.map((r: string) => r.toLowerCase()) || [];
    return rolesNormalized.some((role: string) =>
      userRoles.includes(role) || user.role?.toLowerCase() === role
    );
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isAuthenticated,
        isInitializing,
        authError,
        login,
        logout,
        refreshUser,
        refreshAccessToken,
        hasRole,
        hasAnyRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export function useHasAnyRole(roles: Role[]) {
  const { hasAnyRole } = useAuth();
  return hasAnyRole(roles);
}
