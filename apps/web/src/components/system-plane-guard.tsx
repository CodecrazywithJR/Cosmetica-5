/**
 * System Plane Guard — blocks BUSINESS routes for superuser without active LE.
 *
 * Wraps page content. If superuser has no active LE selected AND the current
 * route is a business route (not /admin/**), shows a prompt to select one.
 *
 * Admin routes (/[locale]/admin/**) always pass through so the superuser
 * can manage legal entities even when none exist yet.
 *
 * Non-superuser users pass through unchanged.
 */

'use client';

import React, { useState, ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useActiveLegalEntity } from '@/lib/active-legal-entity-context';
import LegalEntitySelector from '@/components/legal-entity-selector';

interface SystemPlaneGuardProps {
  children: ReactNode;
}

/**
 * Returns true if the current pathname is an admin route that should
 * bypass the legal-entity requirement.
 *
 * Admin routes follow the pattern: /[locale]/admin/**
 */
function isAdminRoute(pathname: string): boolean {
  // Strip locale prefix (e.g. "/en/admin/..." → check for "/admin/")
  const segments = pathname.split('/').filter(Boolean); // ['en', 'admin', ...]
  return segments.length >= 2 && segments[1] === 'admin';
}

export default function SystemPlaneGuard({ children }: SystemPlaneGuardProps) {
  const pathname = usePathname();
  const t = useTranslations('system');
  const { isSuperuser, isSystemPlane } = useActiveLegalEntity();
  const [showSelector, setShowSelector] = useState(false);

  // Non-superuser → pass through
  if (!isSuperuser) {
    return <>{children}</>;
  }

  // Superuser with LE selected → pass through (business plane)
  if (!isSystemPlane) {
    return <>{children}</>;
  }

  // Superuser without LE on ADMIN route → pass through (admin plane)
  if (isAdminRoute(pathname)) {
    return <>{children}</>;
  }

  // Superuser without LE on BUSINESS route → show guard
  return (
    <div className="system-plane-guard">
      <div className="system-plane-guard-content">
        <div className="system-plane-guard-icon">🏢</div>
        <h2>{t('guard.title')}</h2>
        <p>{t('guard.description')}</p>
        <button
          className="btn-primary"
          onClick={() => setShowSelector(true)}
        >
          {t('actions.select_legal_entity')}
        </button>
      </div>

      {showSelector && (
        <LegalEntitySelector onClose={() => setShowSelector(false)} />
      )}
    </div>
  );
}
