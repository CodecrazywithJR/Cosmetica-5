/**
 * Patient Consent Documents Component
 * 
 * Displays two fixed consent categories with drag & drop upload.
 * 
 * BUSINESS RULES:
 * - Two fixed categories: Privacy Policy (data_processing) and Terms (terms_and_conditions)
 * - One document per category (most recent if multiple exist)
 * - Status (granted/revoked) independent from document presence
 * - All text via i18n, NO hardcoded strings
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { 
  fetchPatientConsents, 
  getConsentDocumentDownloadUrl,
  deleteConsentDocument,
  uploadConsentDocument,
  type ConsentDocument 
} from '@/lib/api/consents';

interface PatientConsentDocumentsProps {
  patientId: string;
}

const CONSENT_TYPES = {
  PRIVACY: 'data_processing',
  TERMS: 'terms_and_conditions'
} as const;

export default function PatientConsentDocuments({ patientId }: PatientConsentDocumentsProps) {
  const t = useTranslations('patients.consentDocuments');
  const tSections = useTranslations('patients.sections');
  
  const [consents, setConsents] = useState<ConsentDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [consentToDelete, setConsentToDelete] = useState<ConsentDocument | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [uploading, setUploading] = useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  
  const [activeDragCategory, setActiveDragCategory] = useState<'privacy' | 'terms' | null>(null);

  useEffect(() => {
    loadConsents();
  }, [patientId]);

  const loadConsents = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await fetchPatientConsents(patientId);
      setConsents(data);
    } catch (err: any) {
      console.error('Failed to load consent documents:', err);
      setError(err.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  const getConsentByType = (type: string): ConsentDocument | null => {
    const filtered = consents.filter(c => c.consent_type === type);
    if (filtered.length === 0) {
      console.warn(`[PatientConsents] No consent found for type: ${type}`);
      return null;
    }
    if (filtered.length === 1) return filtered[0];
    
    return filtered.sort((a, b) => {
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
      if (isNaN(dateA) || isNaN(dateB)) return 0;
      return dateB - dateA;
    })[0];
  };

  const handleView = async (consentId: string) => {
    try {
      const url = await getConsentDocumentDownloadUrl(consentId);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (err: any) {
      console.error('Failed to get download URL:', err);
      setErrorMessage('Failed to open document');
      setTimeout(() => setErrorMessage(''), 5000);
    }
  };

  const handleDownload = async (consentId: string, filename: string) => {
    try {
      const url = await getConsentDocumentDownloadUrl(consentId);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err: any) {
      console.error('Failed to download document:', err);
      setErrorMessage('Failed to download document');
      setTimeout(() => setErrorMessage(''), 5000);
    }
  };

  const handleDeleteClick = (consent: ConsentDocument) => {
    setConsentToDelete(consent);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!consentToDelete) return;

    try {
      setDeleting(true);
      await deleteConsentDocument(consentToDelete.id);
      await loadConsents();
      setShowDeleteModal(false);
      setConsentToDelete(null);
    } catch (err: any) {
      console.error('Failed to delete document:', err);
      setErrorMessage('Failed to delete document');
      setTimeout(() => setErrorMessage(''), 5000);
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setShowDeleteModal(false);
    setConsentToDelete(null);
  };

  const handleUploadClick = (consentId: string) => {
    if (fileInputRef.current) {
      fileInputRef.current.setAttribute('data-consent-id', consentId);
      fileInputRef.current.click();
    }
  };

  const validateFile = (file: File): string | null => {
    const MAX_SIZE = 25 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      return t('uploadErrors.fileTooBig');
    }

    const ALLOWED_TYPES = [
      'application/pdf',
      'image/jpeg',
      'image/jpg',
      'image/png',
      'image/heic',
      'image/heif',
    ];
    
    const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.heic', '.heif'];
    const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    
    if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXTENSIONS.includes(fileExtension)) {
      return t('uploadErrors.invalidFileType');
    }

    return null;
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const consentId = event.target.getAttribute('data-consent-id');
    if (!consentId) {
      setErrorMessage(t('uploadErrors.uploadFailed'));
      setTimeout(() => setErrorMessage(''), 5000);
      event.target.value = '';
      return;
    }

    const validationError = validateFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      setTimeout(() => setErrorMessage(''), 5000);
      event.target.value = '';
      return;
    }

    try {
      setUploading(consentId);
      await uploadConsentDocument(consentId, file);
      await loadConsents();
      setSuccessMessage(t('uploadSuccess'));
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (err: any) {
      console.error('Failed to upload document:', err);
      setErrorMessage(t('uploadErrors.uploadFailed'));
      setTimeout(() => setErrorMessage(''), 5000);
    } finally {
      setUploading(null);
      event.target.value = '';
    }
  };

  const handleDragEnter = (category: 'privacy' | 'terms') => {
    setActiveDragCategory(category);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (e.currentTarget === e.target) {
      setActiveDragCategory(null);
    }
  };

  const handleDrop = async (e: React.DragEvent, consentId: string) => {
    e.preventDefault();
    setActiveDragCategory(null);

    if (uploading) return;

    const file = e.dataTransfer.files?.[0];
    if (!file) {
      setErrorMessage(t('uploadErrors.noFile'));
      setTimeout(() => setErrorMessage(''), 5000);
      return;
    }

    const validationError = validateFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      setTimeout(() => setErrorMessage(''), 5000);
      return;
    }

    try {
      setUploading(consentId);
      await uploadConsentDocument(consentId, file);
      await loadConsents();
      setSuccessMessage(t('uploadSuccess'));
      setTimeout(() => setSuccessMessage(''), 5000);
    } catch (err: any) {
      console.error('Failed to upload document:', err);
      setErrorMessage(t('uploadErrors.uploadFailed'));
      setTimeout(() => setErrorMessage(''), 5000);
    } finally {
      setUploading(null);
    }
  };

  const renderConsentBlock = (
    consentType: string,
    categoryKey: 'privacy' | 'terms'
  ) => {
    const consent = getConsentByType(consentType);
    
    if (!consent) {
      return <div key={consentType} />;
    }

    const categoryLabel = consentType === CONSENT_TYPES.PRIVACY ? 'data_processing' : 'terms_and_conditions';
    const isDragging = activeDragCategory === categoryKey;

    return (
      <div key={consentType} className="border border-gray-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-900">
            {t(`categories.${categoryLabel}`)}
          </h3>
          
          <span
            className={`inline-flex items-center font-medium rounded-full border px-3 py-1 text-sm ${
              consent.status === 'granted'
                ? 'bg-green-100 text-green-800 border-green-200'
                : 'bg-red-100 text-red-800 border-red-200'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                consent.status === 'granted' ? 'bg-green-600' : 'bg-red-600'
              }`}
            />
            {t(`status.${consent.status}`)}
          </span>
        </div>

        {consent.has_document && consent.document_filename ? (
          <div className="bg-gray-50 rounded-md p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <svg
                  className="w-5 h-5 text-gray-400 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                  />
                </svg>
                <span className="text-sm text-gray-700 truncate">
                  {consent.document_filename}
                </span>
              </div>
              
              <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                <button
                  type="button"
                  onClick={() => handleView(consent.id)}
                  className="px-3 py-1 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                >
                  {t('view')}
                </button>
                <button
                  type="button"
                  onClick={() => handleDownload(consent.id, consent.document_filename!)}
                  className="px-3 py-1 text-sm font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
                >
                  {t('download')}
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteClick(consent)}
                  className="px-3 py-1 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
                >
                  {t('delete')}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div
            onDragEnter={() => handleDragEnter(categoryKey)}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, consent.id)}
            className={`rounded-md p-4 border-2 border-dashed transition-colors ${
              isDragging
                ? 'border-blue-400 bg-blue-50'
                : 'border-gray-300 bg-gray-50'
            }`}
          >
            <div className="text-center">
              <svg
                className={`mx-auto h-10 w-10 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p className={`mt-2 text-sm font-medium ${isDragging ? 'text-blue-900' : 'text-gray-700'}`}>
                {isDragging ? t('dragDropArea.titleActive') : t('dragDropArea.title')}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                {t('dragDropArea.description')}
              </p>
              <button
                type="button"
                onClick={() => handleUploadClick(consent.id)}
                disabled={uploading === consent.id}
                className="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading === consent.id ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {t('uploading')}
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    {t('dragDropArea.button')}
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {tSections('consentDocuments')}
        </h2>
        <div className="animate-pulse space-y-4">
          <div className="h-32 bg-gray-200 rounded"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {tSections('consentDocuments')}
        </h2>
        <div className="text-sm text-red-600">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        {tSections('consentDocuments')}
      </h2>

      {successMessage && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3">
          <svg className="w-5 h-5 text-green-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <p className="text-sm text-green-800 font-medium">
            {successMessage}
          </p>
        </div>
      )}

      {errorMessage && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
          <svg className="w-5 h-5 text-red-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <p className="text-sm text-red-800 font-medium">
            {errorMessage}
          </p>
        </div>
      )}
      
      <div className="space-y-4">
        {renderConsentBlock(CONSENT_TYPES.PRIVACY, 'privacy')}
        {renderConsentBlock(CONSENT_TYPES.TERMS, 'terms')}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.heic,.heif,application/pdf,image/jpeg,image/png,image/heic,image/heif"
        onChange={handleFileSelect}
        className="hidden"
      />

      {showDeleteModal && consentToDelete && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              {t('deleteModal.title')}
            </h2>
            
            <p className="text-sm text-gray-700 mb-3">
              {t('deleteModal.message')}
            </p>
            
            <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-sm text-yellow-800">
                ⚠️ {t('deleteModal.warning')}
              </p>
            </div>
            
            <div className="text-sm text-gray-600 mb-6">
              <p className="font-medium">{t(`type.${consentToDelete.consent_type}`)}</p>
              {consentToDelete.document_filename && (
                <p className="text-xs text-gray-500 mt-1">{consentToDelete.document_filename}</p>
              )}
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleDeleteCancel}
                disabled={deleting}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 transition-colors disabled:opacity-50"
              >
                {t('deleteModal.cancel')}
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                disabled={deleting}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleting ? t('deleteModal.deleting') : t('deleteModal.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
