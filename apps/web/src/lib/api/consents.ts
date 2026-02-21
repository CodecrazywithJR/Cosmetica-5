/**
 * Consent Documents API Client
 * 
 * Handles patient consent documents (scanned/signed consent forms).
 */

import apiClient from './api-client';

export type ConsentType = 
  | 'data_processing'
  | 'terms_and_conditions'
  | 'clinical_photos' 
  | 'marketing_photos' 
  | 'newsletter' 
  | 'marketing_messages';
export type ConsentStatus = 'granted' | 'revoked';

export interface ConsentDocument {
  id: string;
  consent_type: ConsentType;
  status: ConsentStatus;
  granted_at: string;
  revoked_at: string | null;
  has_document: boolean;
  document_id: string | null;
  document_filename: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Fetch all consent documents for a patient.
 * 
 * GET /api/v1/clinical/patients/{patient_id}/consents/
 */
export async function fetchPatientConsents(patientId: string): Promise<ConsentDocument[]> {
  return apiClient.get<ConsentDocument[]>(`/api/v1/clinical/patients/${patientId}/consents/`);
}

/**
 * Create a new consent document for a patient.
 * 
 * POST /api/v1/clinical/patients/{patient_id}/consents/
 * 
 * @param patientId - UUID of the patient
 * @param consentType - Type of consent
 * @param status - Consent status (default: 'granted')
 * @param grantedAt - ISO datetime if status is granted (optional)
 * @returns Promise with the created ConsentDocument
 */
export async function createPatientConsent(
  patientId: string,
  consentType: ConsentType,
  status: ConsentStatus = 'granted',
  grantedAt?: string
): Promise<ConsentDocument> {
  const payload: any = {
    consent_type: consentType,
    status: status,
  };
  
  if (grantedAt) {
    payload.granted_at = grantedAt;
  }
  
  return apiClient.post<ConsentDocument>(
    `/api/v1/clinical/patients/${patientId}/consents/`,
    payload
  );
}

/**
 * Get presigned download URL for a consent document.
 * 
 * GET /api/v1/clinical/consents/{consent_id}/document/download/
 */
export async function getConsentDocumentDownloadUrl(consentId: string): Promise<string> {
  const data = await apiClient.get<{ url: string }>(`/api/v1/clinical/consents/${consentId}/document/download/`);
  return data.url;
}

/**
 * Delete consent document (hard delete from MinIO and database).
 * The consent itself remains, only the attached document is removed.
 * 
 * DELETE /api/v1/clinical/consents/{consent_id}/document/
 */
export async function deleteConsentDocument(consentId: string): Promise<void> {
  await apiClient.delete<void>(`/api/v1/clinical/consents/${consentId}/document/`);
}

/**
 * Upload consent document using presigned URL flow.
 * 
 * Flow:
 * 1. POST metadata to backend (filename, content_type, size)
 * 2. Backend returns presigned upload URL
 * 3. PUT file directly to MinIO using presigned URL
 * 
 * POST /api/v1/clinical/consents/{consent_id}/document/
 * 
 * @param consentId - UUID of the consent
 * @param file - File to upload (PDF, JPG, PNG, HEIC, HEIF)
 * @returns Promise that resolves when upload is complete
 * @throws Error if upload fails at any step
 */
export async function uploadConsentDocument(consentId: string, file: File): Promise<void> {
  // Validate file
  const MAX_SIZE = 25 * 1024 * 1024; // 25 MB
  if (file.size > MAX_SIZE) {
    throw new Error('File size exceeds 25MB limit');
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
    throw new Error('Invalid file type. Allowed: PDF, JPG, PNG, HEIC, HEIF');
  }

  // Step 1: POST metadata to backend to get presigned URL
  const metadata = {
    filename: file.name,
    content_type: file.type || 'application/octet-stream',
    size_bytes: file.size,
  };

  let upload_url: string;
  try {
    const response = await apiClient.post<{ upload_url: string }>(
      `/api/v1/clinical/consents/${consentId}/document/`,
      metadata
    );
    upload_url = response.upload_url;
  } catch (error: any) {
    console.error('[uploadConsentDocument] Failed to get upload URL:', error);
    throw new Error(error?.response?.data?.error || 'Failed to get upload URL from server');
  }

  // Step 2: PUT file directly to MinIO using presigned URL
  // NOTE: Direct fetch to MinIO (external service, no JWT needed)
  try {
    const uploadResponse = await fetch(upload_url, {
      method: 'PUT',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
      },
      body: file,
    });

    if (!uploadResponse.ok) {
      throw new Error(`Storage upload failed: ${uploadResponse.status} ${uploadResponse.statusText}`);
    }
  } catch (error: any) {
    console.error('[uploadConsentDocument] Failed to upload to storage:', error);
    throw new Error('Failed to upload file to storage');
  }
}
