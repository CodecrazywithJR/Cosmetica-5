/**
 * TypeScript types - Shared type definitions
 */

export interface Appointment {
  id: string; // UUID
  patient_id: string; // UUID
  patient_name?: string; // SerializerMethodField from backend
  practitioner_id: string; // UUID
  practitioner_name?: string; // SerializerMethodField from backend
  location_id?: string; // UUID
  location_name?: string; // SerializerMethodField from backend
  source: string; // 'calendly' | 'manual'
  status: 'scheduled' | 'confirmed' | 'checked_in' | 'completed' | 'cancelled' | 'no_show';
  scheduled_start: string; // ISO datetime
  scheduled_end?: string; // ISO datetime
  is_deleted: boolean;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface ClinicalChargeProposal {
  id: number;
  patient_id: string; // UUID
  practitioner_id: number;
  title: string;
  description?: string;
  total_amount: number;
  status: 'draft' | 'pending' | 'approved' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface User {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  role: string;
  is_active: boolean;
  must_change_password?: boolean;
}

export interface Patient {
  id: string; // UUID
  first_name: string;
  last_name: string;
  second_last_name?: string;
  email: string;
  phone: string;
  birth_date: string;
  sex: 'M' | 'F' | 'O';
  consent_data_processing: boolean;
  consent_photo_video: boolean;
  consent_whatsapp_contact: boolean;
  row_version: number;
}
