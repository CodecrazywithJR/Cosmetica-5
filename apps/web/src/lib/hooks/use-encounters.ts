/**
 * Encounters hooks - React hooks for encounter management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

export function useEncounter(id: string) {
  return useQuery({
    queryKey: ['encounters', id],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/clinical/encounters/${id}/`);
      return (response as any).data;
    },
  });
}

export function useAddTreatment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: {
      encounterId: string;
      treatmentId: string;
      quantity: number;
      unitPrice?: number;
      notes?: string;
    }) => {
      const response = await apiClient.post(
        `/api/v1/clinical/encounters/${params.encounterId}/treatments/`,
        {
          treatment_id: params.treatmentId,
          quantity: params.quantity,
          unit_price: params.unitPrice,
          notes: params.notes,
        }
      );
      return (response as any).data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['encounters', variables.encounterId] });
      queryClient.invalidateQueries({ queryKey: ['encounters'] });
    },
  });
}

export function useFinalizeEncounter() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (encounterId: string) => {
      const response = await apiClient.post(
        `/api/v1/clinical/encounters/${encounterId}/finalize/`,
        {}
      );
      return (response as any).data;
    },
    onSuccess: (_, encounterId) => {
      queryClient.invalidateQueries({ queryKey: ['encounters', encounterId] });
      queryClient.invalidateQueries({ queryKey: ['encounters'] });
    },
  });
}

export function useUpdateEncounter() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: { chief_complaint?: string; assessment?: string; plan?: string; internal_notes?: string; proposed_treatment?: string; clinical_notes?: string } }) => {
      const response = await apiClient.patch(`/api/v1/clinical/encounters/${id}/`, data);
      return (response as any).data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['encounters', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['encounters'] });
    },
  });
}

interface AttendAppointmentResponse {
  appointment_id: string;
  encounter_id: string;
  appointment_status: string;
  encounter_status: string;
  created: boolean;
}

export function useCreateEncounterFromAppointment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (appointmentId: string): Promise<AttendAppointmentResponse> => {
      const response = await apiClient.post<AttendAppointmentResponse>(
        `/api/v1/clinical/appointments/${appointmentId}/attend/`,
        {}
      );
      return response;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['encounters'] });
    },
  });
}
