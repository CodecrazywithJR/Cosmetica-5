/**
 * usePatientDetails Hook
 * 
 * Fetches and caches full patient details for use in components that need
 * fields not included in the list endpoint (like consent fields).
 * 
 * Background: The backend uses different serializers:
 * - LIST endpoint: returns only ~13 basic fields (NO consent fields)
 * - DETAIL endpoint: returns all 44 fields (including consents)
 * 
 * This hook:
 * 1. Maintains a cache of full patient details
 * 2. Auto-fetches when needed
 * 3. Provides loading/error states
 * 4. Exposes clearCache() for manual invalidation
 */

'use client';

import { useState, useEffect } from 'react';
import { fetchPatientById, type Patient } from '@/lib/api/patients';

// Global cache (shared across all hook instances)
const patientDetailsCache = new Map<string, Patient>();

type UsePatientDetailsResult = {
  patient: Patient | null;
  loading: boolean;
  error: string | null;
};

/**
 * Fetch and cache patient details
 * 
 * @param patientId - Patient UUID
 * @param skip - Skip fetching (useful when data not needed yet)
 * @returns Patient details, loading state, and error
 */
export function usePatientDetails(
  patientId: string,
  skip: boolean = false
): UsePatientDetailsResult {
  const [patient, setPatient] = useState<Patient | null>(
    patientDetailsCache.get(patientId) || null
  );
  const [loading, setLoading] = useState<boolean>(!patientDetailsCache.has(patientId) && !skip);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Skip if already cached or skip flag is true
    if (skip || patientDetailsCache.has(patientId)) {
      setPatient(patientDetailsCache.get(patientId) || null);
      setLoading(false);
      return;
    }

    let cancelled = false;

    const fetchDetails = async () => {
      try {
        setLoading(true);
        setError(null);

        const data = await fetchPatientById(patientId);

        if (!cancelled) {
          patientDetailsCache.set(patientId, data);
          setPatient(data);
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error(`Failed to fetch patient ${patientId}:`, err);
          setError('Failed to load patient details');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchDetails();

    return () => {
      cancelled = true;
    };
  }, [patientId, skip]);

  return { patient, loading, error };
}

/**
 * Clear entire patient details cache
 * 
 * Call this when you know patient data has changed globally
 * (e.g., after creating/updating a patient)
 */
export function clearPatientDetailsCache(): void {
  patientDetailsCache.clear();
}

/**
 * Clear specific patient from cache
 * 
 * Call this when you know a specific patient was updated
 */
export function clearPatientDetailsCacheFor(patientId: string): void {
  patientDetailsCache.delete(patientId);
}

/**
 * Preload patient details into cache
 * 
 * Useful for preloading visible patients in a list
 */
export async function preloadPatientDetails(patientId: string): Promise<void> {
  if (patientDetailsCache.has(patientId)) {
    return; // Already cached
  }

  try {
    const data = await fetchPatientById(patientId);
    patientDetailsCache.set(patientId, data);
  } catch (err) {
    console.error(`Failed to preload patient ${patientId}:`, err);
  }
}
