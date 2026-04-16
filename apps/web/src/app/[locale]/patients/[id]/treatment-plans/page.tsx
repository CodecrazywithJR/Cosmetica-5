'use client';

import React, { useState } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api/api-client';
import { useAuth } from '@/lib/auth-context';
import Unauthorized from '@/components/unauthorized';

/* ── Interfaces ────────────────────────────────────────────── */

interface TreatmentPlanItem {
  id: string;
  patient: string;
  practitioner: string | null;
  practitioner_name: string | null;
  proposal: string;
  sale: string | null;
  package_name: string;
  status: string;
  planned_sessions: number;
  completed_sessions: number;
  remaining_sessions: number;
  progress_percent: number;
  total_price_snapshot: string;
  currency: string;
  activated_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
}

interface TreatmentPlansResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: TreatmentPlanItem[];
}

/* ── Constants ─────────────────────────────────────────────── */

const TREATMENT_PLAN_STATUSES = [
  'draft',
  'active',
  'completed',
  'cancelled',
] as const;

const TP_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  active: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
};

/* ── Page ──────────────────────────────────────────────────── */

export default function TreatmentPlansPage() {
  const params = useParams();
  const patientId = params.id as string;
  const t = useTranslations();
  const locale = useLocale();
  const { user } = useAuth();

  const [tpPage, setTpPage] = useState(1);
  const [tpStatus, setTpStatus] = useState<string | undefined>(undefined);

  /* ── Query ─────────────────────────────────────────────── */

  const queryParams = new URLSearchParams({ patient: patientId });
  if (tpStatus) queryParams.set('status', tpStatus);
  if (tpPage > 1) queryParams.set('page', String(tpPage));

  const { data, isLoading, isError, error } = useQuery<TreatmentPlansResponse>({
    queryKey: ['patient-treatment-plans', patientId, tpPage, tpStatus],
    queryFn: () =>
      apiClient.get<TreatmentPlansResponse>(
        `/api/v1/clinical/treatment-plans/?${queryParams.toString()}`
      ),
    enabled: !!patientId && !!user,
    staleTime: 1000 * 60,
  });

  const totalPages = data ? Math.ceil(data.count / 50) : 0;
  const is403 = isError && (error as any)?.response?.status === 403;

  /* ── 403 → Unauthorized ────────────────────────────────── */

  if (is403) {
    return <Unauthorized />;
  }

  /* ── Render ────────────────────────────────────────────── */

  return (
    <div className="space-y-6">
      <section className="bg-white rounded-lg shadow-sm border border-gray-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {t('patient360.treatmentPlans')}
          </h2>
        </div>

        {/* Filters */}
        <div className="px-6 py-3 border-b border-gray-200 flex flex-wrap items-center gap-3">
          <select
            value={tpStatus ?? ''}
            onChange={(e) => {
              setTpStatus(e.target.value || undefined);
              setTpPage(1);
            }}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">{t('patient360.overview.allStatuses')}</option>
            {TREATMENT_PLAN_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`treatmentPlans.status.${s}`)}
              </option>
            ))}
          </select>
          {tpStatus && (
            <button
              type="button"
              onClick={() => {
                setTpStatus(undefined);
                setTpPage(1);
              }}
              className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md bg-white hover:bg-gray-50"
            >
              {t('patient360.overview.clearFilters')}
            </button>
          )}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">{t('common.loading')}</p>
            </div>
          </div>
        ) : isError ? (
          <div className="p-6">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {t('treatmentPlans.errorLoading')}
            </div>
          </div>
        ) : (
          <>
            {data && data.results.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          {t('treatmentPlans.colDate')}
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          {t('treatmentPlans.colStatus')}
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          {t('treatmentPlans.colSessions')}
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          {t('treatmentPlans.colRemaining')}
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          {t('treatmentPlans.colProgress')}
                        </th>
                        <th className="px-6 py-3" />
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {data.results.map((tp) => (
                        <tr key={tp.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatDate(tp.created_at)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <TpStatusBadge
                              status={tp.status}
                              label={t(`treatmentPlans.status.${tp.status}`)}
                            />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {tp.completed_sessions} / {tp.planned_sessions}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                            {tp.remaining_sessions}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <ProgressBar percent={tp.progress_percent} />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                            <a
                              href="#"
                              className="text-blue-600 hover:text-blue-800 font-medium"
                            >
                              {t('treatmentPlans.view')}
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
                    <p className="text-sm text-gray-600">
                      {t('patient360.overview.results', { count: data.count })}
                      {' · '}
                      {t('patient360.overview.pageOf', { page: tpPage, total: totalPages })}
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={tpPage <= 1}
                        onClick={() => setTpPage((p) => Math.max(1, p - 1))}
                        className="px-3 py-1 text-sm rounded-md border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {t('patient360.overview.previous')}
                      </button>
                      <button
                        type="button"
                        disabled={!data.next}
                        onClick={() => setTpPage((p) => p + 1)}
                        className="px-3 py-1 text-sm rounded-md border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {t('patient360.overview.next')}
                      </button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="p-6 text-center text-sm text-gray-500">
                {t('patient360.noTreatmentPlans')}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

/* ── Helpers ──────────────────────────────────────────────── */

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-';
  try {
    return new Date(dateString).toLocaleDateString();
  } catch {
    return '-';
  }
}

function TpStatusBadge({ status, label }: { status: string; label: string }) {
  const color = TP_STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-800';
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}
    >
      {label}
    </span>
  );
}

function progressColor(percent: number): string {
  if (percent <= 0) return '#d1d5db';
  if (percent >= 100) return '#16a34a';
  return '#2563eb';
}

function ProgressBar({ percent }: { percent: number }) {
  const clamped = Math.min(Math.max(percent, 0), 100);
  return (
    <div className="flex items-center gap-2">
      <div
        style={{
          height: '8px',
          width: '80px',
          backgroundColor: '#e5e7eb',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${clamped}%`,
            backgroundColor: progressColor(clamped),
            borderRadius: '4px',
          }}
        />
      </div>
      <span className="text-xs text-gray-600">{percent}%</span>
    </div>
  );
}
