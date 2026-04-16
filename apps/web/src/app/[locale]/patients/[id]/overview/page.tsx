'use client';

import React, { useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import apiClient from '@/lib/api/api-client';
import { useAuth } from '@/lib/auth-context';
import Unauthorized from '@/components/unauthorized';
import { routes, type Locale } from '@/lib/routing';

interface PatientData {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  birth_date: string | null;
  sex: string | null;
  document_type: string | null;
  document_number: string | null;
  nationality: string | null;
  country_code: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  notes?: string;
  [key: string]: unknown;
}

interface InsuranceData {
  provider_name: string;
  member_number: string | null;
  social_security_number: string | null;
  valid_from: string | null;
  [key: string]: unknown;
}

interface KpisData {
  proposals_draft_count: number;
  proposals_sent_count: number;
  last_sale_date: string | null;
  total_encounters?: number;
  active_treatment_plans_count?: number;
}

interface OverviewResponse {
  patient: PatientData;
  insurance_active: InsuranceData | null;
  kpis: KpisData;
}

interface EncounterListItem {
  id: string;
  patient: string;
  patient_name: string;
  practitioner: string | null;
  practitioner_name: string | null;
  type: string;
  status: string;
  occurred_at: string;
  treatment_count: number;
  attachments_summary: {
    has_photos: boolean;
    has_documents: boolean;
    photo_count: number;
    document_count: number;
  };
  created_at: string;
}

interface EncountersResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: EncounterListItem[];
}

const ENCOUNTER_STATUSES = ['draft', 'finalized', 'cancelled'] as const;

interface ProposalListItem {
  id: string;
  encounter_id: string | null;
  patient_name: string;
  practitioner_name: string | null;
  status: string;
  status_display: string;
  total_amount: string;
  currency: string;
  line_count: number;
  valid_until: string | null;
  sent_at: string | null;
  accepted_at: string | null;
  converted_to_sale: string | null;
  converted_at: string | null;
  created_at: string;
  created_by: string | null;
}

interface ProposalsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ProposalListItem[];
}

const PROPOSAL_STATUSES = ['draft', 'sent', 'accepted', 'cancelled', 'expired'] as const;

export default function OverviewPage() {
  const params = useParams();
  const patientId = params.id as string;
  const t = useTranslations();
  const locale = useLocale() as Locale;
  const { user } = useAuth();

  // Proposals ALV state
  const [propPage, setPropPage] = useState(1);
  const [propStatus, setPropStatus] = useState<string | undefined>(undefined);

  // Encounters ALV state
  const [encPage, setEncPage] = useState(1);
  const [encStatus, setEncStatus] = useState<string | undefined>(undefined);
  const [encDateFrom, setEncDateFrom] = useState<string | undefined>(undefined);
  const [encDateTo, setEncDateTo] = useState<string | undefined>(undefined);

  const resetFilters = useCallback(() => {
    setEncPage(1);
    setEncStatus(undefined);
    setEncDateFrom(undefined);
    setEncDateTo(undefined);
  }, []);

  const { data, isLoading, isError, error } = useQuery<OverviewResponse>({
    queryKey: ['patient-overview', patientId],
    queryFn: () => apiClient.get<OverviewResponse>(`/api/v1/clinical/patients/${patientId}/overview/`),
    enabled: !!patientId && !!user,
    staleTime: 1000 * 60 * 2,
  });

  // Proposals ALV query — fires when overview loaded and financial data is present
  const showProposalsALV = data?.kpis?.proposals_draft_count !== undefined;

  const proposalsQueryParams = new URLSearchParams({ patient: patientId });
  if (propStatus) proposalsQueryParams.set('status', propStatus);
  if (propPage > 1) proposalsQueryParams.set('page', String(propPage));

  const {
    data: propData,
    isLoading: propLoading,
    isError: propIsError,
    error: propError,
  } = useQuery<ProposalsResponse>({
    queryKey: ['patient-proposals', patientId, propPage, propStatus],
    queryFn: () =>
      apiClient.get<ProposalsResponse>(
        `/api/v1/clinical/proposals/?${proposalsQueryParams.toString()}`
      ),
    enabled: !!patientId && !!user && showProposalsALV,
    staleTime: 1000 * 60,
  });

  const propTotalPages = propData ? Math.ceil(propData.count / 50) : 0;
  const prop403 = propIsError && (propError as any)?.response?.status === 403;

  // Encounters ALV query — only fires when overview loaded and clinical data is present
  const showEncountersALV = data?.kpis?.total_encounters !== undefined;

  const encountersQueryParams = new URLSearchParams({ patient_id: patientId });
  if (encStatus) encountersQueryParams.set('status', encStatus);
  if (encDateFrom) encountersQueryParams.set('date_from', encDateFrom);
  if (encDateTo) encountersQueryParams.set('date_to', encDateTo);
  if (encPage > 1) encountersQueryParams.set('page', String(encPage));

  const {
    data: encData,
    isLoading: encLoading,
    isError: encIsError,
    error: encError,
  } = useQuery<EncountersResponse>({
    queryKey: ['patient-encounters', patientId, encPage, encStatus, encDateFrom, encDateTo],
    queryFn: () =>
      apiClient.get<EncountersResponse>(
        `/api/v1/clinical/encounters/?${encountersQueryParams.toString()}`
      ),
    enabled: !!patientId && !!user && showEncountersALV,
    staleTime: 1000 * 60,
  });

  const encTotalPages = encData ? Math.ceil(encData.count / 50) : 0;
  const enc403 = encIsError && (encError as any)?.response?.status === 403;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-sm text-red-800">
          {(error as any)?.response?.data?.detail || t('patient360.overview.errorLoading')}
        </p>
      </div>
    );
  }

  if (!data) return null;

  const { patient, insurance_active, kpis } = data;

  return (
    <div className="space-y-6">
      {/* Personal Data */}
      <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {t('patient360.overview.personalData')}
        </h2>
        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4">
          <DataField label={t('patients.fields.first_name.label')} value={patient.first_name} />
          <DataField label={t('patients.fields.last_name.label')} value={patient.last_name} />
          <DataField label={t('patients.fields.email.label')} value={patient.email} />
          <DataField label={t('patients.fields.phone.label')} value={formatPhone(patient)} />
          <DataField label={t('patients.fields.birth_date.label')} value={formatDate(patient.birth_date)} />
          <DataField label={t('patients.fields.sex.label')} value={patient.sex ? t(`common.sex.${patient.sex}`) : '-'} />
          <DataField label={t('patients.fields.document_type.label')} value={patient.document_type ? t(`patients.documentType.${patient.document_type}`) : '-'} />
          <DataField label={t('patients.fields.document_number.label')} value={patient.document_number} />
          <DataField label={t('patients.fields.nationality.label')} value={patient.nationality} />
          <DataField label={t('patients.fields.emergency_contact_name.label')} value={patient.emergency_contact_name} />
          <DataField label={t('patients.fields.emergency_contact_phone.label')} value={patient.emergency_contact_phone} />
        </dl>
      </section>

      {/* Notes — only rendered if backend returns them (RBAC) */}
      {patient.notes !== undefined && (
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t('patient360.overview.notes')}
          </h2>
          <p className="text-sm text-gray-700 whitespace-pre-wrap">
            {patient.notes || t('patient360.overview.noNotes')}
          </p>
        </section>
      )}

      {/* Active Insurance */}
      {insurance_active && (
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t('patient360.overview.activeCoverage')}
          </h2>
          <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4">
            <DataField label={t('patient360.overview.providerName')} value={insurance_active.provider_name} />
            <DataField label={t('patient360.overview.memberNumber')} value={insurance_active.member_number} />
            <DataField label={t('patient360.overview.socialSecurityNumber')} value={insurance_active.social_security_number} />
            <DataField label={t('patient360.overview.validFrom')} value={formatDate(insurance_active.valid_from)} />
          </dl>
        </section>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Financial KPIs — always shown */}
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t('patient360.overview.financialKpis')}
          </h2>
          <dl className="space-y-3">
            <KpiRow label={t('patient360.overview.proposalsDraft')} value={kpis.proposals_draft_count} />
            <KpiRow label={t('patient360.overview.proposalsSent')} value={kpis.proposals_sent_count} />
            <KpiRow
              label={t('patient360.overview.lastSaleDate')}
              value={kpis.last_sale_date ? formatDate(kpis.last_sale_date) : '-'}
            />
          </dl>
        </section>

        {/* Clinical KPIs — only if backend returns them */}
        {(kpis.total_encounters !== undefined || kpis.active_treatment_plans_count !== undefined) && (
          <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {t('patient360.overview.clinicalKpis')}
            </h2>
            <dl className="space-y-3">
              {kpis.total_encounters !== undefined && (
                <KpiRow label={t('patient360.overview.totalEncounters')} value={kpis.total_encounters} />
              )}
              {kpis.active_treatment_plans_count !== undefined && (
                <KpiRow label={t('patient360.overview.activeTreatmentPlans')} value={kpis.active_treatment_plans_count} />
              )}
            </dl>
          </section>
        )}
      </div>

      {/* ── Proposals ALV ── */}
      {showProposalsALV && (
        <section className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              {t('patient360.overview.financialHistory')}
            </h2>
          </div>

          {prop403 ? (
            <div className="p-6">
              <Unauthorized />
            </div>
          ) : (
            <>
              {/* Filters */}
              <div className="p-4 border-b border-gray-100 flex flex-wrap items-end gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    {t('proposals.detail.title')}
                  </label>
                  <select
                    value={propStatus ?? ''}
                    onChange={(e) => { setPropStatus(e.target.value || undefined); setPropPage(1); }}
                    className="block w-40 rounded-md border-gray-300 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="">{t('patient360.overview.allStatuses')}</option>
                    {PROPOSAL_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {t(`proposals.status.${s}`)}
                      </option>
                    ))}
                  </select>
                </div>

                {propStatus && (
                  <button
                    type="button"
                    onClick={() => { setPropStatus(undefined); setPropPage(1); }}
                    className="text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    {t('patient360.overview.clearFilters')}
                  </button>
                )}
              </div>

              {/* Table */}
              {propLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
                </div>
              ) : propIsError ? (
                <div className="p-6">
                  <p className="text-sm text-red-600">
                    {t('patient360.overview.errorLoadingProposals')}
                  </p>
                </div>
              ) : propData && propData.results.length > 0 ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('patient360.overview.colDate')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('patient360.overview.colStatus')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('patient360.overview.colTotal')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('patient360.overview.colValidUntil')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('patient360.overview.colPractitioner')}
                          </th>
                          <th className="px-6 py-3" />
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {propData.results.map((prop) => (
                          <tr key={prop.id} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {formatDate(prop.created_at)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <ProposalStatusBadge status={prop.status} label={t(`proposals.status.${prop.status}`)} />
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                              {parseFloat(prop.total_amount).toLocaleString(locale, { minimumFractionDigits: 2 })} {prop.currency}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                              {formatDate(prop.valid_until)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                              {prop.practitioner_name ?? '-'}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                              <Link
                                href={routes.proposals.detail(locale, prop.id)}
                                className="text-blue-600 hover:text-blue-800 font-medium"
                              >
                                {t('patient360.overview.viewProposal')}
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  {propTotalPages > 1 && (
                    <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
                      <p className="text-sm text-gray-600">
                        {t('patient360.overview.results', { count: propData.count })}
                        {' · '}
                        {t('patient360.overview.pageOf', { page: propPage, total: propTotalPages })}
                      </p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={propPage <= 1}
                          onClick={() => setPropPage((p) => Math.max(1, p - 1))}
                          className="px-3 py-1 text-sm rounded-md border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {t('patient360.overview.previous')}
                        </button>
                        <button
                          type="button"
                          disabled={!propData.next}
                          onClick={() => setPropPage((p) => p + 1)}
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
                  {t('patient360.overview.noProposals')}
                </div>
              )}
            </>
          )}
        </section>
      )}

      {/* ── Encounters ALV ── */}
      {showEncountersALV && (
        <section className="bg-white rounded-lg shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              {t('patient360.overview.clinicalHistory')}
            </h2>
          </div>

          {enc403 ? (
            <div className="p-6">
              <Unauthorized />
            </div>
          ) : (
            <>
              {/* Filters */}
              <div className="p-4 border-b border-gray-100 flex flex-wrap items-end gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    {t('encounters.list.patient.columns.status')}
                  </label>
                  <select
                    value={encStatus ?? ''}
                    onChange={(e) => { setEncStatus(e.target.value || undefined); setEncPage(1); }}
                    className="block w-40 rounded-md border-gray-300 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="">{t('patient360.overview.allStatuses')}</option>
                    {ENCOUNTER_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {t(`encounters.list.patient.status.${s}`)}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    {t('patient360.overview.dateFrom')}
                  </label>
                  <input
                    type="date"
                    value={encDateFrom ?? ''}
                    onChange={(e) => { setEncDateFrom(e.target.value || undefined); setEncPage(1); }}
                    className="block w-40 rounded-md border-gray-300 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    {t('patient360.overview.dateTo')}
                  </label>
                  <input
                    type="date"
                    value={encDateTo ?? ''}
                    onChange={(e) => { setEncDateTo(e.target.value || undefined); setEncPage(1); }}
                    className="block w-40 rounded-md border-gray-300 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>

                {(encStatus || encDateFrom || encDateTo) && (
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    {t('patient360.overview.clearFilters')}
                  </button>
                )}
              </div>

              {/* Table */}
              {encLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
                </div>
              ) : encIsError ? (
                <div className="p-6">
                  <p className="text-sm text-red-600">
                    {t('patient360.overview.errorLoadingEncounters')}
                  </p>
                </div>
              ) : encData && encData.results.length > 0 ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('encounters.list.patient.columns.date')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('encounters.list.patient.columns.type')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('encounters.list.patient.columns.status')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('encounters.list.patient.columns.practitioner')}
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {t('encounters.list.patient.columns.treatments')}
                          </th>
                          <th className="px-6 py-3" />
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {encData.results.map((enc) => (
                          <tr key={enc.id} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {formatDate(enc.occurred_at)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                              {t(`encounters.list.patient.type.${enc.type}`)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <EncounterStatusBadge status={enc.status} label={t(`encounters.list.patient.status.${enc.status}`)} />
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                              {enc.practitioner_name ?? '-'}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                              {enc.treatment_count}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                              <Link
                                href={routes.encounters.detail(locale, enc.id)}
                                className="text-blue-600 hover:text-blue-800 font-medium"
                              >
                                {t('patient360.overview.viewEncounter')}
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  {encTotalPages > 1 && (
                    <div className="px-6 py-3 border-t border-gray-200 flex items-center justify-between">
                      <p className="text-sm text-gray-600">
                        {t('patient360.overview.results', { count: encData.count })}
                        {' · '}
                        {t('patient360.overview.pageOf', { page: encPage, total: encTotalPages })}
                      </p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          disabled={encPage <= 1}
                          onClick={() => setEncPage((p) => Math.max(1, p - 1))}
                          className="px-3 py-1 text-sm rounded-md border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {t('patient360.overview.previous')}
                        </button>
                        <button
                          type="button"
                          disabled={!encData.next}
                          onClick={() => setEncPage((p) => p + 1)}
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
                  {t('patient360.overview.noEncounters')}
                </div>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}

/* ── Helpers ──────────────────────────────────────────────────── */

function DataField({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</dt>
      <dd className="mt-1 text-sm text-gray-900">{value || '-'}</dd>
    </div>
  );
}

function KpiRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-sm text-gray-600">{label}</dt>
      <dd className="text-sm font-semibold text-gray-900">{value}</dd>
    </div>
  );
}

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-';
  try {
    return new Date(dateString).toLocaleDateString();
  } catch {
    return '-';
  }
}

const ENCOUNTER_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  finalized: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
};

function EncounterStatusBadge({ status, label }: { status: string; label: string }) {
  const color = ENCOUNTER_STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-800';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

const PROPOSAL_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  sent: 'bg-blue-100 text-blue-800',
  accepted: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
  expired: 'bg-gray-100 text-gray-800',
};

function ProposalStatusBadge({ status, label }: { status: string; label: string }) {
  const color = PROPOSAL_STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-800';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function formatPhone(patient: PatientData): string {
  if (!patient.phone) return '-';
  const code = patient.country_code || '';
  return code ? `${code} ${patient.phone}` : patient.phone;
}
