/**
 * Patient Edit Page
 * 
 * Editable form for patient information with optimistic locking.
 * Handles row_version for concurrency control.
 * 
 * Backend integration:
 * - GET /api/v1/clinical/patients/{id}/ (load data)
 * - PATCH /api/v1/clinical/patients/{id}/ (save with row_version)
 */

'use client';

import React, { useState, useEffect, FormEvent } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import { fetchPatientById, updatePatient, type Patient } from '@/lib/api/patients';
import ConsentBadge from '@/components/patients/ConsentBadge';
import { routes, type Locale } from '@/lib/routing';

export default function PatientEditPage() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('patients');
  const tCommon = useTranslations('common');
  
  const patientId = params.id as string;
  
  // State
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>('');
  const [concurrencyError, setConcurrencyError] = useState(false);
  const [originalPatient, setOriginalPatient] = useState<Patient | null>(null);
  
  // Validation state
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [validationBanner, setValidationBanner] = useState(false);
  
  // Dirty state tracking
  const [isDirty, setIsDirty] = useState(false);
  
  // Form state
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
    privacy_policy_accepted_at: null as string | null,
    terms_accepted: false,
    terms_accepted_at: null as string | null,
  });

  // Load patient data on mount
  useEffect(() => {
    loadPatient();
  }, [patientId]);

  const loadPatient = async () => {
    try {
      setLoading(true);
      setError('');
      setConcurrencyError(false);
      
      const data = await fetchPatientById(patientId);
      setOriginalPatient(data);
      
      // Initialize form with patient data
      setFormData({
        first_name: data.first_name || '',
        last_name: data.last_name || '',
        email: data.email || '',
        phone: data.phone || '',
        birth_date: data.birth_date || '',
        sex: data.sex || '',
        document_type: data.document_type || '',
        document_number: data.document_number || '',
        nationality: data.nationality || '',
        emergency_contact_name: data.emergency_contact_name || '',
        emergency_contact_phone: data.emergency_contact_phone || '',
        privacy_policy_accepted: data.privacy_policy_accepted,
        privacy_policy_accepted_at: data.privacy_policy_accepted_at,
        terms_accepted: data.terms_accepted,
        terms_accepted_at: data.terms_accepted_at,
      });
    } catch (err: any) {
      console.error('Failed to load patient:', err);
      
      let errorMsg = t('errors.loadFailed') || 'Error loading patient';
      
      if (err?.response) {
        const status = err.response.status;
        if (status === 401) {
          errorMsg = 'Not authenticated. Please login again.';
        } else if (status === 403) {
          errorMsg = 'No permission to edit this patient.';
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

  // Check if form has unsaved changes
  const checkIsDirty = (): boolean => {
    if (!originalPatient) return false;
    
    // Compare relevant fields
    return (
      formData.first_name !== (originalPatient.first_name || '') ||
      formData.last_name !== (originalPatient.last_name || '') ||
      formData.email !== (originalPatient.email || '') ||
      formData.phone !== (originalPatient.phone || '') ||
      formData.birth_date !== (originalPatient.birth_date || '') ||
      formData.sex !== (originalPatient.sex || '') ||
      formData.document_type !== (originalPatient.document_type || '') ||
      formData.document_number !== (originalPatient.document_number || '') ||
      formData.nationality !== (originalPatient.nationality || '') ||
      formData.emergency_contact_name !== (originalPatient.emergency_contact_name || '') ||
      formData.emergency_contact_phone !== (originalPatient.emergency_contact_phone || '') ||
      formData.privacy_policy_accepted !== originalPatient.privacy_policy_accepted ||
      formData.terms_accepted !== originalPatient.terms_accepted
    );
  };

  // Update dirty state when formData changes
  useEffect(() => {
    setIsDirty(checkIsDirty());
  }, [formData, originalPatient]);

  // Warn user before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  // Validation function
  const validate = (data: typeof formData): { fieldErrors: Record<string, string>, isValid: boolean } => {
    const errors: Record<string, string> = {};
    
    // A) Basic fields
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
    
    if (data.email && data.email.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(data.email)) {
        errors.email = t('errors.invalidEmail');
      }
    }
    
    if (data.phone && data.phone.trim() && data.phone.trim().length < 6) {
      errors.phone = t('errors.minLength', { min: 6 });
    }
    
    if (data.birth_date && data.birth_date.trim()) {
      const date = new Date(data.birth_date);
      if (isNaN(date.getTime())) {
        errors.birth_date = t('errors.invalidDate');
      } else if (date > new Date()) {
        errors.birth_date = t('errors.futureDate');
      }
    }
    
    // B) Document pair consistency
    const hasDocType = data.document_type && data.document_type.trim();
    const hasDocNumber = data.document_number && data.document_number.trim();
    
    if ((hasDocType && !hasDocNumber) || (!hasDocType && hasDocNumber)) {
      errors.document_type = t('errors.documentPairRequired');
      errors.document_number = t('errors.documentPairRequired');
    }
    
    // C) Emergency contact pair consistency
    const hasEmergencyName = data.emergency_contact_name && data.emergency_contact_name.trim();
    const hasEmergencyPhone = data.emergency_contact_phone && data.emergency_contact_phone.trim();
    
    if ((hasEmergencyName && !hasEmergencyPhone) || (!hasEmergencyName && hasEmergencyPhone)) {
      errors.emergency_contact_name = t('errors.pairRequired');
      errors.emergency_contact_phone = t('errors.pairRequired');
    } else if (hasEmergencyPhone && data.emergency_contact_phone.trim().length < 6) {
      errors.emergency_contact_phone = t('errors.minLength', { min: 6 });
    }
    
    // D) Consent timestamp consistency (internal validation)
    if (data.privacy_policy_accepted && !data.privacy_policy_accepted_at) {
      errors.privacy_policy_accepted = 'Internal error: timestamp missing';
    }
    if (data.terms_accepted && !data.terms_accepted_at) {
      errors.terms_accepted = 'Internal error: timestamp missing';
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
    // Trigger validation when field is blurred
    const validation = validate(formData);
    setFieldErrors(validation.fieldErrors);
  };

  const handleConsentChange = (field: 'privacy_policy_accepted' | 'terms_accepted', checked: boolean) => {
    const timestampField = field === 'privacy_policy_accepted' 
      ? 'privacy_policy_accepted_at' 
      : 'terms_accepted_at';
    
    setFormData(prev => {
      const wasAccepted = prev[field];
      
      // If changing from FALSE to TRUE, set timestamp to now
      if (!wasAccepted && checked) {
        return {
          ...prev,
          [field]: checked,
          [timestampField]: new Date().toISOString(),
        };
      }
      
      // If changing from TRUE to FALSE, clear timestamp
      if (wasAccepted && !checked) {
        return {
          ...prev,
          [field]: checked,
          [timestampField]: null,
        };
      }
      
      // If staying TRUE, keep existing timestamp
      return {
        ...prev,
        [field]: checked,
      };
    });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if (!originalPatient) return;
    
    // Mark submit as attempted
    setSubmitAttempted(true);
    
    // Validate form
    const validation = validate(formData);
    setFieldErrors(validation.fieldErrors);
    
    // If invalid, focus first error field and show banner
    if (!validation.isValid) {
      setError(t('errors.formInvalid'));
      
      // Focus first field with error
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
      setConcurrencyError(false);
      
      // Build payload with row_version
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
        emergency_contact_name: formData.emergency_contact_name || null,
        emergency_contact_phone: formData.emergency_contact_phone || null,
        privacy_policy_accepted: formData.privacy_policy_accepted,
        privacy_policy_accepted_at: formData.privacy_policy_accepted_at,
        terms_accepted: formData.terms_accepted,
        terms_accepted_at: formData.terms_accepted_at,
      };
      
      const updatedPatient = await updatePatient(patientId, payload);
      
      // Update originalPatient with new row_version and reset dirty state
      setOriginalPatient(updatedPatient);
      setIsDirty(false);
      
      // Notify other components that patient data changed
      window.dispatchEvent(new Event('patients-updated'));
      
      // Navigate back to detail page
      router.push(routes.patients.detail(locale, patientId));
    } catch (err: any) {
      console.error('Failed to update patient:', err);
      
      let errorMsg = t('errors.updateFailed') || 'Error updating patient';
      
      if (err?.response) {
        const status = err.response.status;
        if (status === 409) {
          // Concurrency conflict
          setConcurrencyError(true);
          errorMsg = t('errors.concurrencyConflict');
        } else if (status === 401) {
          errorMsg = 'Not authenticated. Please login again.';
        } else if (status === 403) {
          errorMsg = 'No permission to update this patient.';
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
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (isDirty) {
      const confirmed = window.confirm(
        `${t('edit.unsavedChanges.title')}\n\n${t('edit.unsavedChanges.body')}`
      );
      if (!confirmed) return;
    }
    router.push(routes.patients.detail(locale, patientId));
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

  if (error && !originalPatient) {
    return (
      <AppLayout>
        <div className="page-header">
          <h1 className="page-title">{t('edit.title')}</h1>
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
            onClick={handleCancel}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
          >
            {t('edit.ctaCancel')}
          </button>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('edit.title')}</h1>
          <p className="page-description">
            {formData.first_name} {formData.last_name}
          </p>
        </div>
      </div>

      <div className="page-content">
        {/* Consent Warning (non-blocking) */}
        {(!formData.privacy_policy_accepted || !formData.terms_accepted) && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-yellow-800 font-medium">
                  {t('warnings.consentsMissing')}
                </p>
                <p className="text-xs text-yellow-700 mt-1">
                  {t('warnings.consentsMissingCta')}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-red-800 font-medium">{error}</p>
                {concurrencyError && (
                  <p className="text-xs text-red-700 mt-1">
                    {t('errors.reloadPrompt')}
                  </p>
                )}
              </div>
              {concurrencyError && (
                <button
                  onClick={() => loadPatient()}
                  className="ml-4 px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors"
                >
                  {t('actions.reload')}
                </button>
              )}
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
                  {t('fields.first_name.label')}
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
                  {t('fields.last_name.label')}
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
            
            {/* Consent Badge Preview */}
            <div className="mb-4">
              <ConsentBadge
                patient={{
                  ...originalPatient!,
                  privacy_policy_accepted: formData.privacy_policy_accepted,
                  terms_accepted: formData.terms_accepted,
                }}
                size="md"
              />
            </div>

            {/* Business Rule Microcopy */}
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm text-blue-800">
                ℹ️ {t('consent.requiredForEncounters')}
              </p>
            </div>

            <div className="space-y-4">
              {/* Privacy Policy */}
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
                  {formData.privacy_policy_accepted_at && (
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(formData.privacy_policy_accepted_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>

              {/* Terms & Conditions */}
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
                  {formData.terms_accepted_at && (
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(formData.terms_accepted_at).toLocaleString()}
                    </p>
                  )}
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
              {t('edit.ctaCancel')}
            </button>
            <button
              type="submit"
              disabled={saving || Object.keys(fieldErrors).length > 0}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving && (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              )}
              {t('edit.ctaSave')}
            </button>
          </div>
        </form>
      </div>
    </AppLayout>
  );
}
