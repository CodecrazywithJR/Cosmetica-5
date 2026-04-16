'use client';

import React from 'react';
import { useParams, usePathname } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import AppLayout from '@/components/layout/app-layout';
import { useAuth, ROLES } from '@/lib/auth-context';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api/api-client';
import ConsentBadge from '@/components/patients/ConsentBadge';
import Unauthorized from '@/components/unauthorized';
import type { Locale } from '@/lib/routing';

interface OverviewResponse {
  patient: {
    id: string;
    first_name: string;
    last_name: string;
    [key: string]: unknown;
  };
  insurance_active: {
    provider_name: string;
    [key: string]: unknown;
  } | null;
  kpis: Record<string, unknown>;
}

interface TabDef {
  key: string;
  labelKey: string;
  href: string;
}

function buildTabs(basePath: string, canViewClinical: boolean): TabDef[] {
  const tabs: TabDef[] = [
    { key: 'overview', labelKey: 'patient360.tabs.overview', href: `${basePath}/overview` },
  ];

  if (canViewClinical) {
    tabs.push(
      { key: 'encounters', labelKey: 'patient360.tabs.encounters', href: `${basePath}/encounters` },
      { key: 'treatment-plans', labelKey: 'patient360.tabs.treatmentPlans', href: `${basePath}/treatment-plans` },
    );
  }

  tabs.push(
    { key: 'proposals', labelKey: 'patient360.tabs.proposals', href: `${basePath}/proposals` },
    { key: 'sales', labelKey: 'patient360.tabs.sales', href: `${basePath}/sales` },
  );

  return tabs;
}

export default function Patient360Layout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const pathname = usePathname();
  const locale = useLocale() as Locale;
  const t = useTranslations();
  const { user, hasAnyRole } = useAuth();

  const patientId = params.id as string;
  const basePath = `/${locale}/patients/${patientId}`;

  // Check if it's an /edit sub-route — if so, skip layout chrome
  const isEditRoute = pathname.endsWith('/edit');
  if (isEditRoute) {
    return <>{children}</>;
  }

  // Role-based access — evaluated against ALL user.roles[], not roles[0]
  const canViewClinical = hasAnyRole([ROLES.ADMIN, ROLES.PRACTITIONER]);
  const canViewFinancial = hasAnyRole([ROLES.ADMIN, ROLES.PRACTITIONER, ROLES.RECEPTION, ROLES.ACCOUNTING]);

  // If user has no allowed role → Unauthorized
  if (user && !canViewFinancial) {
    return <Unauthorized />;
  }

  const tabs = buildTabs(basePath, canViewClinical);

  // Determine active tab from pathname
  const activeSegment = pathname.split('/').pop() || 'overview';

  // Fetch overview for header data
  const { data: overview } = useQuery<OverviewResponse>({
    queryKey: ['patient-overview', patientId],
    queryFn: () => apiClient.get<OverviewResponse>(`/api/v1/clinical/patients/${patientId}/overview/`),
    enabled: !!patientId && !!user,
    staleTime: 1000 * 60 * 2,
  });

  const patientName = overview
    ? `${overview.patient.first_name} ${overview.patient.last_name}`
    : '';

  const insuranceProvider = overview?.insurance_active?.provider_name;

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {patientName || (
                    <span className="inline-block w-48 h-7 bg-gray-200 rounded animate-pulse" />
                  )}
                </h1>
                <div className="flex items-center gap-3 mt-1">
                  {overview && (
                    <ConsentBadge patientId={patientId} size="sm" />
                  )}
                  {insuranceProvider && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                      </svg>
                      {insuranceProvider}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <Link
              href={`${basePath}/edit`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              {t('common.edit')}
            </Link>
          </div>
        </div>

        {/* Tabs */}
        {tabs.length > 0 && (
          <div className="border-b border-gray-200 mb-6">
            <nav className="-mb-px flex space-x-8" aria-label="Tabs">
              {tabs.map((tab) => {
                const isActive = activeSegment === tab.key;
                return (
                  <Link
                    key={tab.key}
                    href={tab.href}
                    className={`whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
                      isActive
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {t(tab.labelKey)}
                  </Link>
                );
              })}
            </nav>
          </div>
        )}

        {/* Content */}
        {children}
      </div>
    </AppLayout>
  );
}
