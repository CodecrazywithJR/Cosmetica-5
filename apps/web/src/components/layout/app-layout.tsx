/**
 * App Layout
 * Main layout with sidebar navigation
 */

'use client';

import React, { ReactNode } from 'react';
import { useAuth, ROLES } from '@/lib/auth-context';
import { useRouter, usePathname } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { LanguageSwitcher } from '@/components/language-switcher';
import { routes, type Locale } from '@/lib/routing';
import { APP_NAME } from '@/lib/constants';

interface AppLayoutProps {
  children: ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const { user, logout, hasAnyRole } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations('nav');
  const tCommon = useTranslations('common');
  const locale = useLocale() as Locale;

  if (!user) {
    router.push(routes.login(locale));
    return null;
  }

  /**
   * Get user display label with fallback strategy.
   * Priority: email (always available from backend) → fallback to translated "User"
   * Note: Backend UserProfile only provides { id, email, is_active, roles }
   * See PROJECT_DECISIONS.md section 12.12 for tech debt details.
   */
  const getUserLabel = (user: { email: string }): string => {
    return user.email || tCommon('user');
  };

  const navigation = [
    {
      name: t('agenda'), // "Agenda" - Internal appointment management
      href: routes.agenda(locale), // Routes to / (home)
      icon: CalendarIcon,
      show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.PRACTITIONER]),
    },
    {
      name: t('schedule'), // "New Appointment" - Calendly booking
      href: routes.schedule(locale), // Routes to /schedule
      icon: PlusCircleIcon,
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
      name: t('admin'),
      href: routes.admin(locale),
      icon: SettingsIcon,
      show: hasAnyRole([ROLES.ADMIN]),
    },
  ];

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
        </nav>

        <div className="sidebar-footer">
          <LanguageSwitcher />
          <button onClick={logout} className="btn-secondary w-full" style={{ marginTop: '12px' }}>
            {t('actions.logout')}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">{children}</main>
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
