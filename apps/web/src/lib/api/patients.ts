/**
 * Patients API - Functions for patient management
 * Endpoints: /api/v1/clinical/patients/
 */

import apiClient from './api-client';

export interface Patient {
  id: string; // UUID
  first_name: string;
  last_name: string;
  second_last_name?: string;
  email: string;
  phone: string;
  birth_date: string; // YYYY-MM-DD
  sex: 'male' | 'female' | 'other' | 'unknown' | null; // Backend uses lowercase full words
  
  // Legal consents (required)
  privacy_policy_accepted: boolean;
  privacy_policy_accepted_at: string | null;
  terms_accepted: boolean;
  terms_accepted_at: string | null;
  
  row_version: number;
  created_at?: string;
  updated_at?: string;
  
  // Computed fields from backend (list view only)
  has_missing_legal_consents?: boolean;  // Checkboxes not marked (BLOCKING)
  has_missing_consent_documents?: boolean;  // Documents not uploaded (INFORMATIVE)
  
  // Additional fields for patient details/edit
  document_type?: 'dni' | 'passport' | 'other' | null;
  document_number?: string;
  nationality?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  country_code?: string;
}

export interface PatientsListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Patient[];
}

/**
 * Fetch patients list with optional search
 * Backend expects query parameter 'q' for full-text search
 * Searches in: first_name, last_name, email, phone, full_name_normalized
 */
export async function fetchPatients(
  search?: string,
  limit?: number
): Promise<PatientsListResponse> {
  const params: Record<string, any> = {};
  if (search) params.q = search; // Backend uses 'q' parameter for search
  if (limit) params.limit = limit;

  return apiClient.get<PatientsListResponse>('/api/v1/clinical/patients/', { params });
}

/**
 * Fetch a single patient by ID (UUID)
 */
export async function fetchPatientById(id: string): Promise<Patient> {
  return apiClient.get<Patient>(`/api/v1/clinical/patients/${id}/`);
}

/**
 * Create new patient
 */
export async function createPatient(data: Partial<Patient>): Promise<Patient> {
  return apiClient.post<Patient>('/api/v1/clinical/patients/', data);
}

/**
 * Update existing patient
 */
export async function updatePatient(
  id: string,
  data: Partial<Patient>
): Promise<Patient> {
  return apiClient.patch<Patient>(`/api/v1/clinical/patients/${id}/`, data);
}

/**
 * Get patient full name
 */
export function getPatientFullName(patient: Patient): string {
  const parts = [
    patient.first_name,
    patient.last_name,
    patient.second_last_name
  ].filter(Boolean);
  return parts.join(' ');
}
