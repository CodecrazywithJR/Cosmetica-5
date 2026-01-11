/**
 * Patients Page
 * 
 * Patient management - List view
 * 
 * Features:
 * - Patient list with search
 * - Real backend integration (no mocks)
 * - Loading, error, and empty states
 * - Responsive table layout
 * 
 * Backend integration:
 * - GET /api/v1/clinical/patients/
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';
import AppLayout from '@/components/layout/app-layout';
import { fetchPatients, getPatientFullName, type Patient } from '@/lib/api/patients';
import ConsentBadge from '@/components/patients/ConsentBadge';
import { routes, type Locale } from '@/lib/routing';
import { mapSexCode } from '@/lib/i18n-utils';
import { clearPatientDetailsCache } from '@/hooks/usePatientDetails';

export default function PatientsPage() {
  const t = useTranslations('patients');
  const tCommon = useTranslations('common');
  const locale = useLocale() as Locale;
  const router = useRouter();
  
  // State
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  const loadPatients = async (search?: string) => {
    try {
      setLoading(true);
      setError('');
      
      // Clear patient details cache to fetch fresh consent data
      clearPatientDetailsCache();
      
      const data = await fetchPatients(search, 100); // Load first 100
      setPatients(data.results);
    } catch (err: any) {
      console.error('Failed to load patients:', err);
      
      let errorMsg = t('errors.loadFailed') || 'Error loading patients';
      
      if (err?.response) {
        const status = err.response.status;
        if (status === 401) {
          errorMsg = 'Not authenticated. Please login again.';
        } else if (status === 403) {
          errorMsg = 'No permission to view patients.';
        } else if (status === 404) {
          errorMsg = 'Patients endpoint not found.';
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

  // Load patients on mount and when patients are updated
  useEffect(() => {
    loadPatients();

    // Listen for patient updates from edit/create pages
    const handlePatientsUpdated = () => {
      console.log('Patients updated event received, reloading list...');
      // Force router revalidation to clear Next.js cache
      router.refresh();
      // Then reload data
      loadPatients(searchQuery);
    };

    window.addEventListener('patients-updated', handlePatientsUpdated);

    return () => {
      window.removeEventListener('patients-updated', handlePatientsUpdated);
    };
  }, []);

  // Reload patients when user navigates back to this page (e.g., from detail page)
  useEffect(() => {
    const handleFocus = () => {
      console.log('🔄 Window focused, reloading patients');
      loadPatients(searchQuery);
    };

    window.addEventListener('focus', handleFocus);

    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, [searchQuery]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadPatients(searchQuery);
  };

  const formatDate = (dateString: string | null): string => {
    if (!dateString) return '-';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return '-';
    }
  };

  const formatPhone = (patient: Patient): string => {
    if (!patient.phone) return '-';
    const code = patient.country_code || '';
    return code ? `${code} ${patient.phone}` : patient.phone;
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

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('title')}</h1>
          <p className="page-description">{t('subtitle')}</p>
        </div>
        <div>
          <button
            onClick={() => router.push(routes.patients.create(locale))}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors flex items-center gap-2"
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
            {t('new')}
          </button>
        </div>
      </div>

      <div className="page-content">
        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center justify-between">
              <p className="text-sm text-red-800">{error}</p>
              <button
                onClick={() => loadPatients()}
                className="ml-4 px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors"
              >
                {tCommon('retry')}
              </button>
            </div>
          </div>
        )}

        {/* Search Bar */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('search_placeholder')}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              {tCommon('search')}
            </button>
            {searchQuery && (
              <button
                type="button"
                onClick={() => {
                  setSearchQuery('');
                  loadPatients();
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
              >
                {tCommon('cancel')}
              </button>
            )}
          </form>
        </div>

        {/* Patients List */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          {patients.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-gray-500 text-lg">{t('no_patients')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('list.columns.name')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('list.columns.email')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('list.columns.phone')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('list.columns.status')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('list.columns.birthDate')}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      {t('list.columns.sex')}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {patients.map((patient) => (
                    <tr 
                      key={patient.id} 
                      onClick={() => router.push(routes.patients.detail(locale, patient.id))}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {getPatientFullName(patient)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">
                          {patient.email || '-'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">
                          {formatPhone(patient)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <ConsentBadge
                          patientId={patient.id}
                          size="sm"
                        />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">
                          {formatDate(patient.birth_date)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-500">
                          {patient.sex ? tCommon(`sex.${mapSexCode(patient.sex)}`) : '-'}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Results Count */}
        {patients.length > 0 && (
          <div className="mt-4 text-sm text-gray-600">
            {patients.length} patient{patients.length !== 1 ? 's' : ''} found
          </div>
        )}
      </div>
    </AppLayout>
  );
}
