/**
 * Encounters hooks - React hooks for encounter management
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';
import { API_ROUTES } from '@/lib/api-config';

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
  const [loading, setLoading] = useState(false);
  
  const addTreatment = async (encounterId: number, data: any) => {
    setLoading(true);
    try {
      console.log(`Add treatment to encounter ${encounterId}`, data);
    } finally {
      setLoading(false);
    }
  };

  return { addTreatment, loading };
}

export function useFinalizeEncounter() {
  const [loading, setLoading] = useState(false);
  
  const finalize = async (encounterId: number) => {
    setLoading(true);
    try {
      console.log(`Finalize encounter ${encounterId}`);
    } finally {
      setLoading(false);
    }
  };

  return { finalize, loading };
}

export function useUpdateEncounter() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: { chief_complaint?: string; assessment?: string; plan?: string; internal_notes?: string } }) => {
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
