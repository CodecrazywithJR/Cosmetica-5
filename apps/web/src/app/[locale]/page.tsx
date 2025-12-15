'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { checkBackendHealth, getPatients, type Patient } from '@/lib/api';

export default function DashboardPage() {
  const t = useTranslations();
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState<string | null>(null);
  
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientsError, setPatientsError] = useState<string | null>(null);

  // Check backend health on mount
  useEffect(() => {
    async function checkHealth() {
      try {
        setHealthLoading(true);
        const status = await checkBackendHealth();
        setHealthStatus(status);
        setHealthError(null);
      } catch (error: any) {
        setHealthError(error.message || 'Connection failed');
        setHealthStatus(null);
      } finally {
        setHealthLoading(false);
      }
    }
    checkHealth();
  }, []);

  // Load patients if backend is healthy
  useEffect(() => {
    async function loadPatients() {
      if (!healthStatus || healthStatus.status !== 'ok') return;
      
      try {
        setPatientsLoading(true);
        const data = await getPatients({ page: 1 });
        setPatients(data.results || []);
        setPatientsError(null);
      } catch (error: any) {
        setPatientsError(error.message || 'Failed to load patients');
      } finally {
        setPatientsLoading(false);
      }
    }
    loadPatients();
  }, [healthStatus]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">
            {t('app.title')}
          </h1>
          <p className="text-gray-600">{t('app.subtitle')}</p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Backend Health Status */}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Backend Connection Status</h2>
          
          {healthLoading && (
            <div className="flex items-center text-blue-600">
              <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {t('health.checking')}
            </div>
          )}

          {healthError && (
            <div className="bg-red-50 border border-red-200 rounded p-4">
              <div className="flex items-center">
                <svg className="h-5 w-5 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                <span className="text-red-700 font-medium">{t('health.disconnected')}</span>
              </div>
              <p className="text-red-600 text-sm mt-2">{healthError}</p>
            </div>
          )}

          {healthStatus && (
            <div className="bg-green-50 border border-green-200 rounded p-4">
              <div className="flex items-center mb-3">
                <svg className="h-5 w-5 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span className="text-green-700 font-medium">{t('health.connected')}</span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">API Status:</span>
                  <span className="ml-2 font-semibold text-green-700">{healthStatus.status}</span>
                </div>
                <div>
                  <span className="text-gray-600">{t('health.database')}:</span>
                  <span className="ml-2 font-semibold text-green-700">{healthStatus.database}</span>
                </div>
                <div>
                  <span className="text-gray-600">{t('health.redis')}:</span>
                  <span className="ml-2 font-semibold text-green-700">{healthStatus.redis}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Patients List */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">{t('patients.list')}</h2>
          
          {patientsLoading && (
            <div className="text-gray-600">{t('common.loading')}</div>
          )}

          {patientsError && (
            <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">
              {patientsError}
            </div>
          )}

          {patients.length === 0 && !patientsLoading && !patientsError && (
            <div className="text-gray-500 text-center py-8">
              {t('patients.no_patients')}
            </div>
          )}

          {patients.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Age</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Phone</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {patients.map((patient) => (
                    <tr key={patient.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{patient.id}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{patient.full_name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{patient.age}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{patient.phone}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{patient.email}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
