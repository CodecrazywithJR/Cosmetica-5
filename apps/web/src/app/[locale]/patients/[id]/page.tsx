/**
 * Patient Detail Page (Read-Only)
 * 
 * Shows complete patient information including consent status.
 * No editing functionality - just displays data fetched from API.
 * 
 * Backend integration:
 * - GET /api/v1/clinical/patients/{id}/
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import { fetchPatientById, type Patient } from '@/lib/api/patients';
import ConsentBadge from '@/components/patients/ConsentBadge';
import { routes, type Locale } from '@/lib/routing';
import { mapSexCode } from '@/lib/i18n-utils';

export default function PatientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('patients');
  const tCommon = useTranslations('common');
  
  const patientId = params.id as string;
  
  // State
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  // Load patient data on mount and when patient is updated
  useEffect(() => {
    loadPatient();

    // Listen for patient updates from edit page
    const handlePatientsUpdated = () => {
      console.log('Patient updated event received, reloading detail...');
      router.refresh();
      loadPatient();
    };

    window.addEventListener('patients-updated', handlePatientsUpdated);

    return () => {
      window.removeEventListener('patients-updated', handlePatientsUpdated);
    };
  }, [patientId]);

  const loadPatient = async () => {
    try {
      setLoading(true);
      setError('');
      
      const data = await fetchPatientById(patientId);
      setPatient(data);
    } catch (err: any) {
      console.error('Failed to load patient:', err);
      
      let errorMsg = t('errors.loadFailed') || 'Error loading patient';
      
      if (err?.response) {
        const status = err.response.status;
        if (status === 401) {
          errorMsg = 'Not authenticated. Please login again.';
        } else if (status === 403) {
          errorMsg = 'No permission to view this patient.';
        } else if (status === 404) {
          errorMsg = 'Patient not found.';
        } else if (status >= 500) {
          errorMsg = 'Server error. Please try again later.';
        }
      } else if (err?.request) {
        errorMsg = 'Cannot connect to server. Check your connection.';
      }
      
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string | null): string => {
    if (!dateString) return '-';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return '-';
    }
  };

  const handleEdit = () => {
    router.push(routes.patients.detail(locale, patientId) + '/edit');
  };

  const handleEditConsents = () => {
    router.push(routes.patients.detail(locale, patientId) + '/edit#consents');
  };

  const handleBackToList = () => {
    router.push(routes.patients.list(locale));
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">{tCommon('loading')}</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  if (error || !patient) {
    return (
      <AppLayout>
        <div className="page-header">
          <h1 className="page-title">{t('detail.title')}</h1>
        </div>
        <div className="page-content">
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center justify-between">
              <p className="text-sm text-red-800">{error}</p>
              <button
                onClick={() => loadPatient()}
                className="ml-4 px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors"
              >
                {tCommon('retry')}
              </button>
            </div>
          </div>
          <button
            onClick={handleBackToList}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
          >
            {t('detail.ctaBack')}
          </button>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('detail.title')}</h1>
          <p className="page-description">
            {patient.first_name} {patient.last_name}
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleBackToList}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
          >
            {t('detail.ctaBack')}
          </button>
          <button
            onClick={handleEdit}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            {t('detail.ctaEdit')}
          </button>
        </div>
      </div>

      <div className="page-content space-y-6">
        {/* Clinical Actions Card */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h2 className="text-lg font-semibold text-gray-900">
                {t('sections.clinicalActions') || 'Clinical Actions'}
              </h2>
              <ConsentBadge
                patientId={patient.id}
                size="sm"
              />
            </div>
            <span
              title={
                !patient.privacy_policy_accepted || !patient.terms_accepted
                  ? t('actions.consentsRequired')
                  : undefined
              }
              className="inline-block"
            >
              <button
                type="button"
                onClick={() => {
                  // TODO: Navigate to create encounter page when it exists
                  alert('Create encounter functionality coming soon');
                }}
                disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
                aria-disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
                className={`px-4 py-2 rounded-md transition-colors flex items-center gap-2 ${
                  !patient.privacy_policy_accepted || !patient.terms_accepted
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed opacity-50'
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                {t('actions.newEncounter')}
              </button>
            </span>
          </div>
          {(!patient.privacy_policy_accepted || !patient.terms_accepted) && (
            <div 
              className="mt-6 p-4 bg-yellow-50 border border-yellow-300 rounded-lg"
              role="alert"
              aria-live="polite"
            >
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                  <svg
                    className="w-6 h-6 text-yellow-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-sm font-semibold text-yellow-900">
                      {t('consents.bannerTitle')}
                    </h3>
                    <ConsentBadge
                      patientId={patient.id}
                      size="sm"
                    />
                  </div>
                  <p className="text-sm text-yellow-800 mb-3">
                    {t('consents.bannerMessage')}
                  </p>
                  <button
                    type="button"
                    onClick={handleEditConsents}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-md hover:bg-yellow-700 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    {t('consents.reviewCta')}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Section 1: Basic Information */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t('sections.basic')}
          </h2>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.first_name.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.first_name || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.last_name.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.last_name || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.email.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.email || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.phone.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.phone || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.birth_date.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {formatDate(patient.birth_date)}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.sex.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.sex ? tCommon(`sex.${mapSexCode(patient.sex)}`) : '-'}
              </dd>
            </div>
          </dl>
        </div>

        {/* Section 2: Official Identification */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t('sections.identity')}
          </h2>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.document_type.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.document_type 
                  ? t(`documentType.${patient.document_type}`) 
                  : '-'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.document_number.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.document_number || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.nationality.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.nationality || '-'}
              </dd>
            </div>
          </dl>
        </div>

        {/* Section 3: Emergency Contact */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t('sections.emergency')}
          </h2>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.emergency_contact_name.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.emergency_contact_name || '-'}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.emergency_contact_phone.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.emergency_contact_phone || '-'}
              </dd>
            </div>
          </dl>
        </div>

        {/* Section 4: Legal Consents */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t('sections.consent')}
          </h2>
          
          <div className="mb-4">
            <ConsentBadge
              patientId={patient.id}
              size="md"
            />
          </div>

          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
            <p className="text-sm text-blue-800">
              ℹ️ {t('consent.requiredForEncounters')}
            </p>
          </div>

          <dl className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.privacy_policy_accepted.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.privacy_policy_accepted ? tCommon('yes') : tCommon('no')}
              </dd>
              {patient.privacy_policy_accepted_at && (
                <dd className="mt-1 text-xs text-gray-500">
                  {formatDate(patient.privacy_policy_accepted_at)}
                </dd>
              )}
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">
                {t('fields.terms_accepted.label')}
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {patient.terms_accepted ? tCommon('yes') : tCommon('no')}
              </dd>
              {patient.terms_accepted_at && (
                <dd className="mt-1 text-xs text-gray-500">
                  {formatDate(patient.terms_accepted_at)}
                </dd>
              )}
            </div>
          </dl>
        </div>
      </div>
    </AppLayout>
  );
}
