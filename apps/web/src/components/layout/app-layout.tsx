/**
 * App Layout
 * Main layout with sidebar navigation
 */

'use client';

import React, { ReactNode, useState } from 'react';
import { useAuth, ROLES } from '@/lib/auth-context';
import { useRouter, usePathname } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { LanguageSwitcher } from '@/components/language-switcher';
import SystemPlaneGuard from '@/components/system-plane-guard';
import LegalEntitySelector from '@/components/legal-entity-selector';
import { useActiveLegalEntity } from '@/lib/active-legal-entity-context';
import { routes, type Locale } from '@/lib/routing';
import { APP_NAME } from '@/lib/constants';

interface AppLayoutProps {
  children: ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const { user, logout, hasAnyRole, hasRole, isInitializing, authError } = useAuth();
  const {
    isSuperuser,
    isBusinessPlane,
    activeLegalEntity,
    clearLegalEntity,
  } = useActiveLegalEntity();
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations('nav');
  const tUsers = useTranslations('users');
  const tCommon = useTranslations('common');
  const tAdmin = useTranslations('admin');
  const tSystem = useTranslations('system');
  const locale = useLocale() as Locale;
  const [showLESelector, setShowLESelector] = useState(false);

  // While the initial silent token refresh is in-flight, render nothing.
  // While the initial silent token refresh is in-flight, render nothing.
  // This prevents a redirect to /login caused by the brief window where
  // user===null before the async refresh resolves (e.g. on locale switch).
  if (isInitializing) {
    return null;
  }

  // Only redirect to login when:
  // 1) isInitializing is false (refresh attempt completed)
  // 2) user is null (not authenticated)
  // 3) authError is true (refresh definitively failed, not just "not checked yet")
  if (!user && authError) {
    router.push(routes.login(locale));
    return null;
  }

  // Still loading user after successful token refresh — do not redirect, just wait
  if (!user) {
    return null;
  }

  // Redirect to must-change-password if required (but allow access to that page itself)
  if (user.must_change_password && !pathname.includes('/must-change-password')) {
    router.push(routes.mustChangePassword(locale));
    return null;
  }

  /**
   * Get user display label with fallback strategy.
   * Priority: first_name + last_name → email → fallback to translated "User"
   * Updated to show first_name + last_name per branding requirements.
   */
  const getUserLabel = (user: { email: string; first_name?: string; last_name?: string }): string => {
    if (user.first_name && user.last_name) {
      return `${user.first_name} ${user.last_name}`.trim();
    }
    if (user.first_name) {
      return user.first_name;
    }
    if (user.last_name) {
      return user.last_name;
    }
    return user.email || tCommon('user');
  };

  const navigation = [
    {
      name: t('agenda'), // "Agenda" - Internal appointment management
      href: routes.agenda(locale), // Routes to / (home)
      icon: CalendarIcon,
      show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.PRACTITIONER]),
    },
    // {
    //   name: t('schedule'), // REMOVED: Route /schedule does not exist (404)
    //   href: routes.schedule(locale), // Contradicts PROJECT_DECISIONS.md §17.1
    //   icon: PlusCircleIcon,
    //   show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.PRACTITIONER]),
    // },
    {
      name: t('booking'), // "Book Appointment" - Native booking system (Sprint 4)
      href: routes.booking(locale), // Routes to /booking
      icon: ClockIcon,
      show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.PRACTITIONER]),
    },
    {
      name: t('patients'),
      href: routes.patients.list(locale),
      icon: UsersIcon,
      show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.PRACTITIONER]),
    },
    {
      name: t('encounters'),
      href: routes.encounters.list(locale),
      icon: ClipboardIcon,
      show: hasAnyRole([ROLES.ADMIN, ROLES.PRACTITIONER]),
    },
    {
      name: t('proposals'),
      href: routes.proposals.list(locale),
      icon: FileTextIcon,
      show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.ACCOUNTING]),
    },
    {
      name: t('sales'),
      href: routes.sales.list(locale),
      icon: ShoppingCartIcon,
      show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.ACCOUNTING]),
    },
    {
      name: tUsers('title'), // "Gestión de usuarios" - Only for ADMIN (Administración removed per user request)
      href: routes.users.list(locale),
      icon: UsersShieldIcon,
      show: hasRole(ROLES.ADMIN),
    },
  ];

  // Admin section — visible to superuser OR ADMIN role
  const showAdmin = user.is_superuser || hasRole(ROLES.ADMIN);
  const adminNavigation = showAdmin
    ? [
        {
          name: tAdmin('legalEntities.title'),
          href: routes.legalEntities.list(locale),
          icon: BuildingIcon,
        },
      ]
    : [];

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>{APP_NAME}</h2>
          <div className="user-info">
            <span className="user-name">{getUserLabel(user)}</span>
            <span className="user-roles">{user.roles.join(', ')}</span>
          </div>
        </div>

        <nav className="sidebar-menu">
          {navigation
            .filter((item) => item.show)
            .map((item) => {
              const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`sidebar-item ${isActive ? 'active' : ''}`}
                >
                  <item.icon className="sidebar-icon" />
                  <span>{item.name}</span>
                </Link>
              );
            })}

          {/* Admin section */}
          {adminNavigation.length > 0 && (
            <>
              <div style={{ borderTop: '1px solid var(--gray-200, #e5e7eb)', margin: '12px 0 8px', opacity: 0.5 }} />
              <div style={{ padding: '4px 16px', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--gray-400, #9ca3af)' }}>
                {tAdmin('section')}
              </div>
              {adminNavigation.map((item) => {
                const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`sidebar-item ${isActive ? 'active' : ''}`}
                  >
                    <item.icon className="sidebar-icon" />
                    <span>{item.name}</span>
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          {/* Superuser LE indicator — replaces the old header bar */}
          {isSuperuser && isBusinessPlane && activeLegalEntity && (
            <div style={{
              padding: '10px 12px',
              marginBottom: 10,
              background: 'var(--gray-50, #f9fafb)',
              borderRadius: 8,
              border: '1px solid var(--gray-200, #e5e7eb)',
              fontSize: 13,
            }}>
              <div style={{ fontWeight: 600, color: 'var(--gray-700, #374151)', marginBottom: 6, lineHeight: 1.3 }}>
                {activeLegalEntity.legal_name}
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  className="btn-secondary btn-sm"
                  style={{ flex: 1, fontSize: 12, padding: '4px 8px' }}
                  onClick={() => setShowLESelector(true)}
                >
                  {tSystem('actions.switch_legal_entity')}
                </button>
                <button
                  className="btn-secondary btn-sm"
                  style={{ flex: 1, fontSize: 12, padding: '4px 8px' }}
                  onClick={clearLegalEntity}
                >
                  {tSystem('actions.return_to_system')}
                </button>
              </div>
            </div>
          )}
          <LanguageSwitcher />
          <button onClick={logout} className="btn-secondary w-full" style={{ marginTop: '12px' }}>
            {t('actions.logout')}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <SystemPlaneGuard>
          {children}
        </SystemPlaneGuard>
      </main>

      {/* LE selector modal — triggered from sidebar */}
      {showLESelector && (
        <LegalEntitySelector onClose={() => setShowLESelector(false)} />
      )}
    </div>
  );
}

// Simple icons (can replace with lucide-react or heroicons)
function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  );
}

function PlusCircleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function UsersIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
      />
    </svg>
  );
}

function ClipboardIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
      />
    </svg>
  );
}

function FileTextIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function ShoppingCartIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"
      />
    </svg>
  );
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function UsersShieldIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14zm-4 6v-7.5l4-2.222"
      />
    </svg>
  );
}

function BuildingIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
      />
    </svg>
  );
}
