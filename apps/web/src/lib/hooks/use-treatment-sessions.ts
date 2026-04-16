/**
 * Treatment Session hooks - React hooks for treatment session management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

export interface TreatmentSession {
  id: string;
  treatment_plan: string;
  appointment: string | null;
  practitioner: string | null;
  practitioner_name: string | null;
  patient: string;
  package_name: string;
  status: 'draft' | 'completed' | 'cancelled';
  notes: string;
  performed_at: string | null;
  created_at: string;
  updated_at: string;
}

export function useTreatmentSession(id: string) {
  return useQuery<TreatmentSession>({
    queryKey: ['treatment-sessions', id],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/clinical/treatment-sessions/${id}/`);
      return (response as any).data ?? response;
    },
    enabled: !!id,
  });
}

export function useUpdateTreatmentSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: { notes?: string; performed_at?: string } }) => {
      const response = await apiClient.patch(`/api/v1/clinical/treatment-sessions/${id}/`, data);
      return (response as any).data ?? response;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['treatment-sessions', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['treatment-sessions'] });
    },
  });
}

export function useCompleteTreatmentSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await apiClient.post(`/api/v1/clinical/treatment-sessions/${id}/complete/`, {});
      return (response as any).data ?? response;
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['treatment-sessions', id] });
      queryClient.invalidateQueries({ queryKey: ['treatment-sessions'] });
      queryClient.invalidateQueries({ queryKey: ['treatment-plans'] });
    },
  });
}

export function useCancelTreatmentSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await apiClient.post(`/api/v1/clinical/treatment-sessions/${id}/cancel/`, {});
      return (response as any).data ?? response;
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['treatment-sessions', id] });
      queryClient.invalidateQueries({ queryKey: ['treatment-sessions'] });
      queryClient.invalidateQueries({ queryKey: ['treatment-plans'] });
    },
  });
}
