'use client';

import React, { useEffect, useRef, useState, FormEvent } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';

import AppLayout from '@/components/layout/app-layout';
import { fetchPatientById, updatePatient, type Patient } from '@/lib/api/patients';
import {
  fetchPatientConsents,
  uploadConsentDocument,
  deleteConsentDocument,
  getConsentDocumentDownloadUrl,
  type ConsentDocument,
} from '@/lib/api/consents';

import { routes, type Locale } from '@/lib/routing';

const CONSENT_TYPES = {
  PRIVACY: 'data_processing',
  TERMS: 'terms_and_conditions',
} as const;

export default function PatientEditPage() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale() as Locale;

  const t = useTranslations('patients');
  const tCommon = useTranslations('common');

  // Extract and validate patient ID from URL params (UUID)
  const patientId = params.id as string;

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [originalPatient, setOriginalPatient] = useState<Patient | null>(null);

  const [consents, setConsents] = useState<ConsentDocument[]>([]);
  const [loadingConsents, setLoadingConsents] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [activeDragCategory, setActiveDragCategory] = useState<'privacy' | 'terms' | null>(null);

  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [showSuccessModal, setShowSuccessModal] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [consentToDelete, setConsentToDelete] = useState<ConsentDocument | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    birth_date: '',
    sex: '' as '' | 'female' | 'male' | 'other' | 'unknown',
    document_type: '' as '' | 'dni' | 'passport' | 'other',
    document_number: '',
    nationality: '',
    country_code: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    privacy_policy_accepted: false,
    privacy_policy_accepted_at: null as string | null,
    terms_accepted: false,
    terms_accepted_at: null as string | null,
  });

  useEffect(() => {
    // Only load patient if we have a valid UUID
    if (patientId && patientId.length > 0) {
      loadPatient();
    } else {
      setLoading(false);
      setError('Invalid patient ID');
    }
  }, [patientId]);

  async function loadPatient() {
    if (!patientId || patientId.length === 0) {
      setError('Invalid patient ID');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError('');
      const patient = await fetchPatientById(patientId);
      setOriginalPatient(patient);
      setFormData({
        first_name: patient.first_name || '',
        last_name: patient.last_name || '',
        email: patient.email || '',
        phone: patient.phone || '',
        birth_date: patient.birth_date || '',
        sex: patient.sex || '',
        document_type: patient.document_type || '',
        document_number: patient.document_number || '',
        nationality: patient.nationality || '',
        country_code: patient.country_code || '',
        emergency_contact_name: patient.emergency_contact_name || '',
        emergency_contact_phone: patient.emergency_contact_phone || '',
        privacy_policy_accepted: patient.privacy_policy_accepted || false,
        privacy_policy_accepted_at: patient.privacy_policy_accepted_at || null,
        terms_accepted: patient.terms_accepted || false,
        terms_accepted_at: patient.terms_accepted_at || null,
      });
      await loadConsents();
    } catch {
      setError(t('errors.loadFailed'));
    } finally {
      setLoading(false);
    }
  }

  async function loadConsents() {
    if (!patientId || patientId.length === 0) return;

    try {
      setLoadingConsents(true);
      const data = await fetchPatientConsents(patientId.toString());
      setConsents(data);
    } finally {
      setLoadingConsents(false);
    }
  }

  function getConsentByType(type: string) {
    const list = consents.filter(c => c.consent_type === type);
    if (!list.length) return null;
    return list.sort(
      (a, b) =>
        new Date(b.created_at ?? 0).getTime() -
        new Date(a.created_at ?? 0).getTime(),
    )[0];
  }

  function handleConsentToggle(
    field: 'privacy_policy_accepted' | 'terms_accepted',
    checked: boolean,
  ) {
    const ts =
      field === 'privacy_policy_accepted'
        ? 'privacy_policy_accepted_at'
        : 'terms_accepted_at';

    setFormData(prev => ({
      ...prev,
      [field]: checked,
      [ts]: checked ? new Date().toISOString() : null,
    }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!originalPatient || !patientId || patientId.length === 0) return;

    try {
      setSaving(true);
      setError('');
      setErrorMessage('');
      setSuccessMessage('');
      
      const payload: any = {
        row_version: originalPatient.row_version,
        first_name: formData.first_name,
        last_name: formData.last_name,
        email: formData.email || null,
        phone: formData.phone || null,
        birth_date: formData.birth_date || null,
        sex: formData.sex || null,
        document_type: formData.document_type || null,
        document_number: formData.document_number || null,
        nationality: formData.nationality || null,
        country_code: formData.country_code || null,
        emergency_contact_name: formData.emergency_contact_name || null,
        emergency_contact_phone: formData.emergency_contact_phone || null,
        privacy_policy_accepted: formData.privacy_policy_accepted,
        privacy_policy_accepted_at: formData.privacy_policy_accepted_at,
        terms_accepted: formData.terms_accepted,
        terms_accepted_at: formData.terms_accepted_at,
      };
      
      await updatePatient(patientId, payload);
      window.dispatchEvent(new Event('patients-updated'));
      setShowSuccessModal(true);
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || t('errors.updateFailed') || 'Error al actualizar paciente';
      setErrorMessage(errorMsg);
    } finally {
      setSaving(false);
    }
  }

  const handleModalClose = () => {
    setShowSuccessModal(false);
    router.push(routes.patients.list(locale));
  };

  async function handleUpload(consentId: string, file: File) {
    try {
      setUploading(consentId);
      await uploadConsentDocument(consentId, file);
      await loadConsents();
      setSuccessMessage(t('consentDocuments.uploadSuccess'));
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch {
      setErrorMessage(t('consentDocuments.uploadErrors.uploadFailed'));
      setTimeout(() => setErrorMessage(''), 5000);
    } finally {
      setUploading(null);
    }
  }

  async function handleDelete() {
    if (!consentToDelete) return;
    try {
      setDeleting(true);
      await deleteConsentDocument(consentToDelete.id);
      await loadConsents();
      setShowDeleteModal(false);
      setConsentToDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('edit.title')}</h1>
        </div>
      </div>

      <div className="page-content">
        {/* Loading State */}
        {loading && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
              <p className="text-sm text-blue-800 font-medium">Cargando paciente...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-800 font-medium">{error}</p>
          </div>
        )}

        {/* Success Message Banner */}
        {successMessage && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-sm text-green-800 font-medium">{successMessage}</p>
          </div>
        )}

        {/* Error Message Banner */}
        {errorMessage && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-800 font-medium">{errorMessage}</p>
          </div>
        )}

        {/* Consent Warning */}
        {!loading && formData && (!formData.privacy_policy_accepted || !formData.terms_accepted) && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-yellow-800">
                  {t('consents.bannerTitle') || 'Consentimientos Legales Requeridos'}
                </p>
                <p className="text-sm text-yellow-700 mt-1">
                  {t('consents.bannerMessage') || 'Este paciente no ha aceptado los consentimientos legales necesarios. No se pueden crear consultas clínicas hasta que se acepten tanto la política de privacidad como los términos y condiciones.'}
                </p>
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Section 1: Basic Information */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {t('sections.basic')}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.first_name.label')} *
                </label>
                <input
                  type="text"
                  name="first_name"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.first_name.help')}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.last_name.label')} *
                </label>
                <input
                  type="text"
                  name="last_name"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.last_name.help')}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.email.label')}
                </label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.email.help')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.phone.label')}
                </label>
                <input
                  type="tel"
                  name="phone"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.phone.help')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.birth_date.label')}
                </label>
                <input
                  type="date"
                  name="birth_date"
                  value={formData.birth_date}
                  onChange={(e) => setFormData({ ...formData, birth_date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.sex.label')}
                </label>
                <select
                  value={formData.sex}
                  onChange={(e) => setFormData({ ...formData, sex: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">-</option>
                  <option value="female">{tCommon('sex.female')}</option>
                  <option value="male">{tCommon('sex.male')}</option>
                  <option value="other">{tCommon('sex.other')}</option>
                  <option value="unknown">{tCommon('sex.unknown')}</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Official Identification */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {t('sections.identity')}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.document_type.label')}
                </label>
                <select
                  name="document_type"
                  value={formData.document_type}
                  onChange={(e) => setFormData({ ...formData, document_type: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">-</option>
                  <option value="dni">{t('documentType.dni')}</option>
                  <option value="passport">{t('documentType.passport')}</option>
                  <option value="other">{t('documentType.other')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.document_number.label')}
                </label>
                <input
                  type="text"
                  name="document_number"
                  value={formData.document_number}
                  onChange={(e) => setFormData({ ...formData, document_number: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.document_number.help')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.nationality.label')}
                </label>
                <input
                  type="text"
                  value={formData.nationality}
                  onChange={(e) => setFormData({ ...formData, nationality: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.nationality.help')}
                />
              </div>
            </div>
          </div>

          {/* Section 3: Emergency Contact */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {t('sections.emergency')}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.emergency_contact_name.label')}
                </label>
                <input
                  type="text"
                  name="emergency_contact_name"
                  value={formData.emergency_contact_name}
                  onChange={(e) => setFormData({ ...formData, emergency_contact_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.emergency_contact_name.help')}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.emergency_contact_phone.label')}
                </label>
                <input
                  type="tel"
                  name="emergency_contact_phone"
                  value={formData.emergency_contact_phone}
                  onChange={(e) => setFormData({ ...formData, emergency_contact_phone: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('fields.emergency_contact_phone.help')}
                />
              </div>
            </div>
          </div>

          {/* Section 4: Legal Consents */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {t('sections.consent')}
            </h2>

            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm text-blue-800">
                ℹ️ {t('consent.requiredForEncounters') || 'Los consentimientos son necesarios para crear consultas'}
              </p>
            </div>

            <div className="space-y-6">
              {/* Privacy Policy Consent */}
              <div className="space-y-3">
                {/* Checkbox ARRIBA */}
                <div className="flex items-start">
                  <div className="flex items-center h-5">
                    <input
                      id="privacy_policy_accepted"
                      type="checkbox"
                      checked={formData.privacy_policy_accepted}
                      onChange={(e) => handleConsentToggle('privacy_policy_accepted', e.target.checked)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                  </div>
                  <div className="ml-3">
                    <label htmlFor="privacy_policy_accepted" className="text-sm font-medium text-gray-700">
                      {t('fields.privacy_policy_accepted.label')}
                    </label>
                    <p className="text-xs text-gray-500 mt-1">
                      {t('fields.privacy_policy_accepted.help')}
                    </p>
                  </div>
                </div>

                {/* Landing Zone ABAJO */}
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-3 bg-gray-50">
                  <p className="text-xs font-medium text-gray-700 mb-2">
                    Documento escaneado (opcional)
                  </p>
                  {(() => {
                    const consent = getConsentByType(CONSENT_TYPES.PRIVACY);
                    if (!consent) {
                      return (
                        <div className="text-center py-4">
                          <p className="text-xs text-gray-500">Marca el checkbox para habilitar la carga de documentos</p>
                        </div>
                      );
                    }
                    return consent.has_document && consent.document_filename ? (
                      <div className="flex items-center justify-between bg-white rounded p-2 border border-gray-200">
                        <div className="flex items-center gap-2 min-w-0">
                          <svg className="w-4 h-4 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span className="text-xs text-gray-700 truncate">{consent.document_filename}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={async () => {
                              const url = await getConsentDocumentDownloadUrl(consent.id);
                              window.open(url, '_blank');
                            }}
                            className="text-blue-600 hover:text-blue-700 text-xs"
                          >
                            Ver
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setConsentToDelete(consent);
                              setShowDeleteModal(true);
                            }}
                            className="text-red-600 hover:text-red-700 text-xs"
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div
                        onDragOver={(e) => e.preventDefault()}
                        onDragEnter={() => setActiveDragCategory('privacy')}
                        onDragLeave={() => setActiveDragCategory(null)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setActiveDragCategory(null);
                          const file = e.dataTransfer.files?.[0];
                          if (file) handleUpload(consent.id, file);
                        }}
                        className={`text-center py-4 ${activeDragCategory === 'privacy' ? 'bg-blue-50 border-blue-300' : ''}`}
                      >
                        <svg className="mx-auto h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        <p className="mt-1 text-xs text-gray-600">
                          {uploading === consent.id ? 'Subiendo...' : (
                            <>
                              Arrastra aquí o
                              <label className="ml-1 text-blue-600 hover:text-blue-700 cursor-pointer">
                                selecciona
                                <input
                                  type="file"
                                  accept=".pdf,.jpg,.jpeg,.png,.heic,.heif"
                                  onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) handleUpload(consent.id, file);
                                  }}
                                  className="hidden"
                                  disabled={uploading === consent.id}
                                />
                              </label>
                            </>
                          )}
                        </p>
                        <p className="text-xs text-gray-400 mt-1">PDF, JPG, PNG, HEIC (máx. 25MB)</p>
                      </div>
                    );
                  })()}
                </div>
              </div>

              {/* Terms & Conditions Consent */}
              <div className="space-y-3">
                {/* Checkbox ARRIBA */}
                <div className="flex items-start">
                  <div className="flex items-center h-5">
                    <input
                      id="terms_accepted"
                      type="checkbox"
                      checked={formData.terms_accepted}
                      onChange={(e) => handleConsentToggle('terms_accepted', e.target.checked)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                  </div>
                  <div className="ml-3">
                    <label htmlFor="terms_accepted" className="text-sm font-medium text-gray-700">
                      {t('fields.terms_accepted.label')}
                    </label>
                    <p className="text-xs text-gray-500 mt-1">
                      {t('fields.terms_accepted.help')}
                    </p>
                  </div>
                </div>

                {/* Landing Zone ABAJO */}
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-3 bg-gray-50">
                  <p className="text-xs font-medium text-gray-700 mb-2">
                    Documento escaneado (opcional)
                  </p>
                  {(() => {
                    const consent = getConsentByType(CONSENT_TYPES.TERMS);
                    if (!consent) {
                      return (
                        <div className="text-center py-4">
                          <p className="text-xs text-gray-500">Marca el checkbox para habilitar la carga de documentos</p>
                        </div>
                      );
                    }
                    return consent.has_document && consent.document_filename ? (
                      <div className="flex items-center justify-between bg-white rounded p-2 border border-gray-200">
                        <div className="flex items-center gap-2 min-w-0">
                          <svg className="w-4 h-4 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <span className="text-xs text-gray-700 truncate">{consent.document_filename}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={async () => {
                              const url = await getConsentDocumentDownloadUrl(consent.id);
                              window.open(url, '_blank');
                            }}
                            className="text-blue-600 hover:text-blue-700 text-xs"
                          >
                            Ver
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setConsentToDelete(consent);
                              setShowDeleteModal(true);
                            }}
                            className="text-red-600 hover:text-red-700 text-xs"
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div
                        onDragOver={(e) => e.preventDefault()}
                        onDragEnter={() => setActiveDragCategory('terms')}
                        onDragLeave={() => setActiveDragCategory(null)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setActiveDragCategory(null);
                          const file = e.dataTransfer.files?.[0];
                          if (file) handleUpload(consent.id, file);
                        }}
                        className={`text-center py-4 ${activeDragCategory === 'terms' ? 'bg-blue-50 border-blue-300' : ''}`}
                      >
                        <svg className="mx-auto h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                        <p className="mt-1 text-xs text-gray-600">
                          {uploading === consent.id ? 'Subiendo...' : (
                            <>
                              Arrastra aquí o
                              <label className="ml-1 text-blue-600 hover:text-blue-700 cursor-pointer">
                                selecciona
                                <input
                                  type="file"
                                  accept=".pdf,.jpg,.jpeg,.png,.heic,.heif"
                                  onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) handleUpload(consent.id, file);
                                  }}
                                  className="hidden"
                                  disabled={uploading === consent.id}
                                />
                              </label>
                            </>
                          )}
                        </p>
                        <p className="text-xs text-gray-400 mt-1">PDF, JPG, PNG, HEIC (máx. 25MB)</p>
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => router.push(routes.patients.list(locale))}
              disabled={saving}
              className="px-6 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors disabled:opacity-50"
            >
              {tCommon('cancel')}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving && (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              )}
              {saving ? tCommon('actions.saving') : tCommon('save')}
            </button>
          </div>
        </form>

        {/* Delete Modal */}
        {showDeleteModal && consentToDelete && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                {t('consentDocuments.deleteModal.title')}
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                {t('consentDocuments.deleteModal.message')}
              </p>
              <p className="text-sm text-yellow-600 mb-6">
                {t('consentDocuments.deleteModal.warning')}
              </p>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowDeleteModal(false);
                    setConsentToDelete(null);
                  }}
                  disabled={deleting}
                  className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 transition-colors disabled:opacity-50"
                >
                  {t('consentDocuments.deleteModal.cancel')}
                </button>
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting}
                  className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors disabled:opacity-50"
                >
                  {deleting ? t('consentDocuments.deleteModal.deleting') : t('consentDocuments.deleteModal.confirm')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success Modal */}
        {showSuccessModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
              <div className="text-center">
                <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100 mb-4">
                  <svg className="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  {t('edit.successTitle') || 'Paciente actualizado'}
                </h3>
                <p className="text-sm text-gray-500 mb-6">
                  {t('edit.successMessage') || 'El paciente ha sido actualizado correctamente.'}
                </p>
                <button
                  onClick={handleModalClose}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  {tCommon('ok') || 'Aceptar'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
