/**
 * Patient Create Page
 * 
 * Form for creating new patients.
 * 
 * NOTE: Backend POST endpoint exists but frontend implementation is pending.
 * Form is ready but save button is disabled with clear messaging.
 * 
 * Backend integration (when ready):
 * - POST /api/v1/clinical/patients/
 */

'use client';

import React, { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import { routes, type Locale } from '@/lib/routing';
import { createPatient } from '@/lib/api/patients';

export default function PatientCreatePage() {
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('patients');
  const tCommon = useTranslations('common');
  
  // State
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>('');
  
  // Form state (same structure as edit)
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
    emergency_contact_name: '',
    emergency_contact_phone: '',
    privacy_policy_accepted: false,
    terms_accepted: false,
  });

  // Validation state
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  // Validation function (same as edit)
  const validate = (data: typeof formData): { fieldErrors: Record<string, string>, isValid: boolean } => {
    const errors: Record<string, string> = {};
    
    // Basic fields (required)
    if (!data.first_name || data.first_name.trim().length < 2) {
      errors.first_name = data.first_name ? t('errors.minLength', { min: 2 }) : t('errors.required');
    } else if (data.first_name.length > 100) {
      errors.first_name = t('errors.maxLength', { max: 100 });
    }
    
    if (!data.last_name || data.last_name.trim().length < 2) {
      errors.last_name = data.last_name ? t('errors.minLength', { min: 2 }) : t('errors.required');
    } else if (data.last_name.length > 100) {
      errors.last_name = t('errors.maxLength', { max: 100 });
    }
    
    // Email (optional but validated if provided)
    if (data.email && data.email.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(data.email)) {
        errors.email = t('errors.invalidEmail');
      }
    }
    
    // Phone (optional but validated if provided)
    if (data.phone && data.phone.trim() && data.phone.trim().length < 6) {
      errors.phone = t('errors.minLength', { min: 6 });
    }
    
    // Birth date validation
    if (data.birth_date && data.birth_date.trim()) {
      const date = new Date(data.birth_date);
      if (isNaN(date.getTime())) {
        errors.birth_date = t('errors.invalidDate');
      } else if (date > new Date()) {
        errors.birth_date = t('errors.futureDate');
      }
    }
    
    // Document pair consistency
    const hasDocType = data.document_type && data.document_type.trim();
    const hasDocNumber = data.document_number && data.document_number.trim();
    
    if ((hasDocType && !hasDocNumber) || (!hasDocType && hasDocNumber)) {
      errors.document_type = t('errors.documentPairRequired');
      errors.document_number = t('errors.documentPairRequired');
    }
    
    // Emergency contact pair consistency
    const hasEmergencyName = data.emergency_contact_name && data.emergency_contact_name.trim();
    const hasEmergencyPhone = data.emergency_contact_phone && data.emergency_contact_phone.trim();
    
    if ((hasEmergencyName && !hasEmergencyPhone) || (!hasEmergencyName && hasEmergencyPhone)) {
      errors.emergency_contact_name = t('errors.pairRequired');
      errors.emergency_contact_phone = t('errors.pairRequired');
    } else if (hasEmergencyPhone && data.emergency_contact_phone.trim().length < 6) {
      errors.emergency_contact_phone = t('errors.minLength', { min: 6 });
    }
    
    return {
      fieldErrors: errors,
      isValid: Object.keys(errors).length === 0
    };
  };

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Revalidate if field was touched or submit attempted
    if (touched[field] || submitAttempted) {
      setTimeout(() => {
        const validation = validate({ ...formData, [field]: value });
        setFieldErrors(validation.fieldErrors);
      }, 0);
    }
  };

  const handleBlur = (field: string) => {
    setTouched(prev => ({ ...prev, [field]: true }));
    const validation = validate(formData);
    setFieldErrors(validation.fieldErrors);
  };

  const handleConsentChange = (field: 'privacy_policy_accepted' | 'terms_accepted', checked: boolean) => {
    setFormData(prev => ({
      ...prev,
      [field]: checked,
    }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    // Mark submit as attempted
    setSubmitAttempted(true);
    
    // Validate form
    const validation = validate(formData);
    setFieldErrors(validation.fieldErrors);
    
    // If invalid, focus first error field
    if (!validation.isValid) {
      setError(t('errors.formInvalid'));
      const firstErrorField = Object.keys(validation.fieldErrors)[0];
      if (firstErrorField) {
        const element = document.querySelector(`[name="${firstErrorField}"]`) as HTMLElement;
        element?.focus();
      }
      return;
    }
    
    try {
      setSaving(true);
      setError('');
      
      // Build payload
      const payload: any = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        email: formData.email || null,
        phone: formData.phone || null,
        birth_date: formData.birth_date || null,
        sex: formData.sex || null,
        document_type: formData.document_type || null,
        document_number: formData.document_number || null,
        nationality: formData.nationality || null,
        emergency_contact_name: formData.emergency_contact_name || null,
        emergency_contact_phone: formData.emergency_contact_phone || null,
        privacy_policy_accepted: formData.privacy_policy_accepted,
        privacy_policy_accepted_at: formData.privacy_policy_accepted ? new Date().toISOString() : null,
        terms_accepted: formData.terms_accepted,
        terms_accepted_at: formData.terms_accepted ? new Date().toISOString() : null,
      };
      
      const newPatient = await createPatient(payload);
      
      // Notify other components that a new patient was created
      window.dispatchEvent(new Event('patients-updated'));
      
      // Navigate to patient detail
      router.push(routes.patients.detail(locale, newPatient.id));
    } catch (err: any) {
      console.error('Failed to create patient:', err);
      
      let errorMsg = t('errors.createFailed') || 'Error al crear paciente';
      
      if (err?.response) {
        const status = err.response.status;
        if (status === 401) {
          errorMsg = 'No autenticado. Por favor inicie sesión nuevamente.';
        } else if (status === 403) {
          errorMsg = 'No tiene permisos para crear pacientes.';
        } else if (status === 400) {
          errorMsg = t('errors.validation') || 'Error de validación. Revise los campos.';
        } else if (status >= 500) {
          errorMsg = 'Error del servidor. Intente nuevamente más tarde.';
        }
      } else if (err?.request) {
        errorMsg = 'No se puede conectar al servidor. Verifique su conexión.';
      }
      
      setError(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    router.push(routes.patients.list(locale));
  };

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('new')}</h1>
          <p className="page-description">
            {t('create.description') || 'Crear nuevo registro de paciente'}
          </p>
        </div>
      </div>

      <div className="page-content">
        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-800 font-medium">{error}</p>
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
                  onChange={(e) => handleInputChange('first_name', e.target.value)}
                  onBlur={() => handleBlur('first_name')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.first_name || submitAttempted) && fieldErrors.first_name 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                  placeholder={t('fields.first_name.help')}
                  required
                />
                {(touched.first_name || submitAttempted) && fieldErrors.first_name && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.first_name}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.last_name.label')} *
                </label>
                <input
                  type="text"
                  name="last_name"
                  value={formData.last_name}
                  onChange={(e) => handleInputChange('last_name', e.target.value)}
                  onBlur={() => handleBlur('last_name')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.last_name || submitAttempted) && fieldErrors.last_name 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                  placeholder={t('fields.last_name.help')}
                  required
                />
                {(touched.last_name || submitAttempted) && fieldErrors.last_name && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.last_name}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.email.label')}
                </label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  onBlur={() => handleBlur('email')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.email || submitAttempted) && fieldErrors.email 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                  placeholder={t('fields.email.help')}
                />
                {(touched.email || submitAttempted) && fieldErrors.email && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.email}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.phone.label')}
                </label>
                <input
                  type="tel"
                  name="phone"
                  value={formData.phone}
                  onChange={(e) => handleInputChange('phone', e.target.value)}
                  onBlur={() => handleBlur('phone')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.phone || submitAttempted) && fieldErrors.phone 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                  placeholder={t('fields.phone.help')}
                />
                {(touched.phone || submitAttempted) && fieldErrors.phone && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.phone}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.birth_date.label')}
                </label>
                <input
                  type="date"
                  name="birth_date"
                  value={formData.birth_date}
                  onChange={(e) => handleInputChange('birth_date', e.target.value)}
                  onBlur={() => handleBlur('birth_date')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.birth_date || submitAttempted) && fieldErrors.birth_date 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                />
                {(touched.birth_date || submitAttempted) && fieldErrors.birth_date && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.birth_date}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.sex.label')}
                </label>
                <select
                  value={formData.sex}
                  onChange={(e) => handleInputChange('sex', e.target.value)}
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
                  onChange={(e) => handleInputChange('document_type', e.target.value)}
                  onBlur={() => handleBlur('document_type')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.document_type || submitAttempted) && fieldErrors.document_type 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                >
                  <option value="">-</option>
                  <option value="dni">{t('documentType.dni')}</option>
                  <option value="passport">{t('documentType.passport')}</option>
                  <option value="other">{t('documentType.other')}</option>
                </select>
                {(touched.document_type || submitAttempted) && fieldErrors.document_type && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.document_type}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.document_number.label')}
                </label>
                <input
                  type="text"
                  name="document_number"
                  value={formData.document_number}
                  onChange={(e) => handleInputChange('document_number', e.target.value)}
                  onBlur={() => handleBlur('document_number')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.document_number || submitAttempted) && fieldErrors.document_number 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                  placeholder={t('fields.document_number.help')}
                />
                {(touched.document_number || submitAttempted) && fieldErrors.document_number && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.document_number}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.nationality.label')}
                </label>
                <input
                  type="text"
                  value={formData.nationality}
                  onChange={(e) => handleInputChange('nationality', e.target.value)}
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
                  onChange={(e) => handleInputChange('emergency_contact_name', e.target.value)}
                  onBlur={() => handleBlur('emergency_contact_name')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.emergency_contact_name || submitAttempted) && fieldErrors.emergency_contact_name 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                  placeholder={t('fields.emergency_contact_name.help')}
                />
                {(touched.emergency_contact_name || submitAttempted) && fieldErrors.emergency_contact_name && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.emergency_contact_name}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('fields.emergency_contact_phone.label')}
                </label>
                <input
                  type="tel"
                  name="emergency_contact_phone"
                  value={formData.emergency_contact_phone}
                  onChange={(e) => handleInputChange('emergency_contact_phone', e.target.value)}
                  onBlur={() => handleBlur('emergency_contact_phone')}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    (touched.emergency_contact_phone || submitAttempted) && fieldErrors.emergency_contact_phone 
                      ? 'border-red-300' 
                      : 'border-gray-300'
                  }`}
                  placeholder={t('fields.emergency_contact_phone.help')}
                />
                {(touched.emergency_contact_phone || submitAttempted) && fieldErrors.emergency_contact_phone && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.emergency_contact_phone}</p>
                )}
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
                ℹ️ {t('consent.requiredForEncounters')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <input
                    id="privacy_policy_accepted"
                    type="checkbox"
                    checked={formData.privacy_policy_accepted}
                    onChange={(e) => handleConsentChange('privacy_policy_accepted', e.target.checked)}
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

              <div className="flex items-start">
                <div className="flex items-center h-5">
                  <input
                    id="terms_accepted"
                    type="checkbox"
                    checked={formData.terms_accepted}
                    onChange={(e) => handleConsentChange('terms_accepted', e.target.checked)}
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
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={handleCancel}
              disabled={saving}
              className="px-6 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors disabled:opacity-50"
            >
              {tCommon('cancel')}
            </button>
            <button
              type="submit"
              disabled={saving || Object.keys(fieldErrors).length > 0}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving && (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              )}
              {saving ? tCommon('actions.saving') : tCommon('save')}
            </button>
          </div>
        </form>
      </div>
    </AppLayout>
  );
}
