/**
 * Active Legal Entity Context — Superuser plane switching.
 *
 * Manages the "active legal entity" state for superusers:
 * - Persists in localStorage (NOT a token — just a preference).
 * - Syncs across tabs via BroadcastChannel('active-le').
 * - No effect for non-superuser users.
 */

'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  ReactNode,
} from 'react';
import { useAuth } from '@/lib/auth-context';
import { setActiveLegalEntityIdProvider } from '@/lib/api/api-client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface LegalEntitySummary {
  id: string;
  legal_name: string;
  trade_name?: string | null;
  country_code?: string;
  city?: string | null;
  is_active?: boolean;
}

interface ActiveLegalEntityContextType {
  /** Currently selected LE (null = System Plane) */
  activeLegalEntity: LegalEntitySummary | null;
  /** ID only — for header injection */
  activeLegalEntityId: string | null;
  /** True when the actor is superuser */
  isSuperuser: boolean;
  /** True when superuser has selected an LE (Business Plane) */
  isBusinessPlane: boolean;
  /** True when superuser has NOT selected an LE (System Plane) */
  isSystemPlane: boolean;
  /** Select a legal entity (switch to Business Plane) */
  selectLegalEntity: (le: LegalEntitySummary) => void;
  /** Clear selection (return to System Plane) */
  clearLegalEntity: () => void;
}

const ActiveLegalEntityContext = createContext<ActiveLegalEntityContextType | undefined>(undefined);

const LS_KEY = 'activeLegalEntityId';
const LS_DATA_KEY = 'activeLegalEntityData';
const BC_CHANNEL = 'active-le';

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ActiveLegalEntityProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const isSuperuser = Boolean(user?.is_superuser);

  const [activeLegalEntity, setActiveLegalEntity] = useState<LegalEntitySummary | null>(null);
  const channelRef = useRef<BroadcastChannel | null>(null);

  // Hydrate from localStorage on mount (SSR-safe)
  useEffect(() => {
    if (typeof window === 'undefined' || !isSuperuser) return;

    try {
      const storedData = localStorage.getItem(LS_DATA_KEY);
      if (storedData) {
        const parsed: LegalEntitySummary = JSON.parse(storedData);
        if (parsed && parsed.id) {
          setActiveLegalEntity(parsed);
        }
      }
    } catch {
      // Corrupted data — clear it
      localStorage.removeItem(LS_KEY);
      localStorage.removeItem(LS_DATA_KEY);
    }
  }, [isSuperuser]);

  // BroadcastChannel setup
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const channel = new BroadcastChannel(BC_CHANNEL);
    channelRef.current = channel;

    channel.onmessage = (event: MessageEvent) => {
      if (!event?.data?.type) return;

      if (event.data.type === 'ACTIVE_LE_CHANGED' && event.data.legalEntity) {
        setActiveLegalEntity(event.data.legalEntity);
      }

      if (event.data.type === 'ACTIVE_LE_CLEARED') {
        setActiveLegalEntity(null);
      }
    };

    return () => {
      channel.close();
      channelRef.current = null;
    };
  }, []);

  // Clear LE state when user is not superuser
  useEffect(() => {
    if (!isSuperuser && activeLegalEntity) {
      setActiveLegalEntity(null);
      if (typeof window !== 'undefined') {
        localStorage.removeItem(LS_KEY);
        localStorage.removeItem(LS_DATA_KEY);
      }
    }
  }, [isSuperuser, activeLegalEntity]);

  const selectLegalEntity = useCallback((le: LegalEntitySummary) => {
    setActiveLegalEntity(le);

    if (typeof window !== 'undefined') {
      localStorage.setItem(LS_KEY, le.id);
      localStorage.setItem(LS_DATA_KEY, JSON.stringify(le));
    }

    channelRef.current?.postMessage({
      type: 'ACTIVE_LE_CHANGED',
      legalEntity: le,
    });
  }, []);

  const clearLegalEntity = useCallback(() => {
    setActiveLegalEntity(null);

    if (typeof window !== 'undefined') {
      localStorage.removeItem(LS_KEY);
      localStorage.removeItem(LS_DATA_KEY);
    }

    channelRef.current?.postMessage({ type: 'ACTIVE_LE_CLEARED' });
  }, []);

  const activeLegalEntityId = activeLegalEntity?.id ?? null;

  // Wire ApiClient: always return latest active LE ID
  const activeLegalEntityIdRef = useRef<string | null>(activeLegalEntityId);
  useEffect(() => {
    activeLegalEntityIdRef.current = activeLegalEntityId;
  }, [activeLegalEntityId]);

  useEffect(() => {
    setActiveLegalEntityIdProvider(() => activeLegalEntityIdRef.current);
  }, []);

  return (
    <ActiveLegalEntityContext.Provider
      value={{
        activeLegalEntity,
        activeLegalEntityId,
        isSuperuser,
        isBusinessPlane: isSuperuser && activeLegalEntityId !== null,
        isSystemPlane: isSuperuser && activeLegalEntityId === null,
        selectLegalEntity,
        clearLegalEntity,
      }}
    >
      {children}
    </ActiveLegalEntityContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useActiveLegalEntity() {
  const context = useContext(ActiveLegalEntityContext);
  if (!context) {
    throw new Error('useActiveLegalEntity must be used within ActiveLegalEntityProvider');
  }
  return context;
}
