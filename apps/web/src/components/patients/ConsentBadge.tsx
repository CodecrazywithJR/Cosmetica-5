/**
 * ConsentBadge Component
 * 
 * Displays patient consent status (privacy policy + terms acceptance)
 * 
 * IMPORTANT: Due to backend API design, the list endpoint does NOT return
 * consent fields. This component fetches full patient details to display
 * accurate consent status.
 * 
 * Usage:
 * ```tsx
 * <ConsentBadge patientId={patient.id} size="sm" />
 * ```
 */

'use client';

import { useTranslations } from 'next-intl';
import { hasRequiredConsents } from '@/lib/patients/consents';
import { usePatientDetails } from '@/hooks/usePatientDetails';

type ConsentBadgeProps = {
  patientId: string;
  size?: 'sm' | 'md';
};

export default function ConsentBadge({ 
  patientId, 
  size = 'md' 
}: ConsentBadgeProps) {
  const t = useTranslations('patients.consent');
  
  // Fetch full patient details (includes consent fields)
  const { patient, loading, error } = usePatientDetails(patientId);
  
  // Size classes
  const sizeClasses = size === 'sm' 
    ? 'px-2 py-0.5 text-xs' 
    : 'px-3 py-1 text-sm';
  
  // Loading state
  if (loading) {
    return (
      <span
        className={`inline-flex items-center font-medium rounded-full border ${sizeClasses} bg-gray-100 text-gray-500 border-gray-200 animate-pulse`}
        role="status"
        aria-label="Loading..."
      >
        <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-gray-400" aria-hidden="true" />
        ...
      </span>
    );
  }
  
  // Error state (show as missing consents)
  if (error || !patient) {
    return (
      <span
        className={`inline-flex items-center font-medium rounded-full border ${sizeClasses} bg-red-100 text-red-800 border-red-200`}
        role="status"
        aria-label="Error"
        title={error || 'Failed to load'}
      >
        <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-red-600" aria-hidden="true" />
        Error
      </span>
    );
  }
  
  // Evaluate consent status
  const allConsentsAccepted = hasRequiredConsents(patient);
  const label = allConsentsAccepted ? t('ok') : t('missing');
  
  // Color classes based on consent status
  const colorClasses = allConsentsAccepted
    ? 'bg-green-100 text-green-800 border-green-200'
    : 'bg-yellow-100 text-yellow-800 border-yellow-200';
  
  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border ${sizeClasses} ${colorClasses}`}
      role="status"
      aria-label={label}
    >
      {/* Status indicator dot */}
      <span
        className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
          allConsentsAccepted ? 'bg-green-600' : 'bg-yellow-600'
        }`}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
