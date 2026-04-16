/**
 * TypeScript types - Shared type definitions
 */

export interface Appointment {
  id: string; // UUID
  patient_id: string; // UUID
  patient_name?: string; // SerializerMethodField from backend
  practitioner_id: string; // UUID
  practitioner_name?: string; // SerializerMethodField from backend
  clinic_id?: string; // UUID
  clinic_name?: string; // SerializerMethodField from backend
  appointment_type_id?: string; // UUID
  appointment_type_name?: string; // SerializerMethodField from backend
  duration_planned?: number;
  source: string; // 'erp' | 'public_api' | 'manual'
  status: 'scheduled' | 'confirmed' | 'checked_in' | 'completed' | 'cancelled' | 'no_show';
  scheduled_start: string; // ISO datetime
  scheduled_end?: string; // ISO datetime
  is_deleted: boolean;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export type ProposalStatus = 'draft' | 'sent' | 'accepted' | 'cancelled' | 'expired';

export interface ProposalLine {
  id: string; // UUID
  treatment_id: string;
  treatment_name: string;
  quantity: number;
  unit_price: string; // Decimal as string
  total_price: string;
  type: 'per_session' | 'full_package';
  notes?: string;
}

export interface ClinicalChargeProposal {
  id: string; // UUID
  patient: {
    id: string;
    full_name: string;
    email: string;
  };
  practitioner: {
    id: string;
    display_name: string;
  };
  encounter_id?: string;
  lines: ProposalLine[];
  total_amount: string; // Decimal as string
  currency: string;
  status: ProposalStatus;
  valid_until?: string; // ISO date
  sent_at?: string;
  accepted_at?: string;
  cancelled_at?: string;
  cancellation_reason?: string;
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
