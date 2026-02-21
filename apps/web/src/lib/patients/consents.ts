/**
 * Patient consents utilities
 * 
 * IMPORTANT: Uses fields from Patient model directly:
 * - privacy_policy_accepted: boolean
 * - privacy_policy_accepted_at: datetime | null
 * - terms_accepted: boolean
 * - terms_accepted_at: datetime | null
 */

import type { Patient } from '@/lib/api/patients';

/**
 * Check if patient has all REQUIRED LEGAL consents
 * (privacy_policy AND terms_and_conditions)
 * 
 * Note: Document upload is OPTIONAL. The boolean flags are sufficient.
 */
export function hasRequiredConsents(patient: Patient): boolean {
  return (
    patient.privacy_policy_accepted === true &&
    patient.terms_accepted === true
  );
}

/**
 * Get consent status summary for LEGAL consents only
 */
export function getConsentStatus(patient: Patient) {
  const total = 2; // privacy_policy + terms_and_conditions
  const granted = [
    patient.privacy_policy_accepted,
    patient.terms_accepted,
  ].filter(Boolean).length;

  return {
    total,
    granted,
    pending: total - granted,
    isComplete: granted === total,
  };
}
