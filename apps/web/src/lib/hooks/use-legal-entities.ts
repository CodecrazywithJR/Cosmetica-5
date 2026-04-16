/**
 * Legal Entities hooks — React hooks for legal entity management
 * Uses /api/v1/system/legal-entities/ endpoints (superuser-only)
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

export interface LegalEntity {
  id: string;
  legal_name: string;
  trade_name: string;
  country_code: string;
  city: string;
  legal_email: string;
  siren: string;
  siret: string;
  vat_number: string;
  is_active: boolean;
  user_count: number;
  created_at: string;
  updated_at: string;
}

export interface LegalEntityDetail extends LegalEntity {
  address_line_1: string;
  address_line_2: string;
  postal_code: string;
  currency: string;
  timezone: string;
  invoice_footer_text: string;
  phone: string;
}

export interface LegalEntityCreateData {
  legal_name: string;
  trade_name?: string;
  address_line_1?: string;
  address_line_2?: string;
  postal_code?: string;
  city?: string;
  country_code: string;
  siren?: string;
  siret?: string;
  vat_number?: string;
  currency?: string;
  timezone?: string;
  legal_email: string;
  phone?: string;
  admin_email: string;
  admin_first_name?: string;
  admin_last_name?: string;
}

export interface LegalEntityUpdateData {
  legal_name?: string;
  trade_name?: string;
  address_line_1?: string;
  address_line_2?: string;
  postal_code?: string;
  city?: string;
  country_code?: string;
  siren?: string;
  siret?: string;
  vat_number?: string;
  currency?: string;
  timezone?: string;
  invoice_footer_text?: string;
  legal_email?: string;
  phone?: string;
  is_active?: boolean;
}

interface LegalEntityListResponse {
  count: number;
  results: LegalEntity[];
}

export function useLegalEntities() {
  return useQuery<LegalEntity[]>({
    queryKey: ['legal-entities'],
    queryFn: async () => {
      const response = await apiClient.get<LegalEntityListResponse>(
        '/api/v1/system/legal-entities/'
      );
      return response.results || [];
    },
  });
}

export function useLegalEntity(id: string) {
  return useQuery<LegalEntityDetail>({
    queryKey: ['legal-entities', id],
    queryFn: async () => {
      const response = await apiClient.get<LegalEntityDetail>(
        `/api/v1/system/legal-entities/${id}/`
      );
      return (response as any).data ?? response;
    },
    enabled: !!id,
  });
}

export function useCreateLegalEntity() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: LegalEntityCreateData) => {
      const response = await apiClient.post(
        '/api/v1/system/legal-entities/',
        data
      );
      return (response as any).data ?? response;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['legal-entities'] });
    },
  });
}

export function useUpdateLegalEntity() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: LegalEntityUpdateData }) => {
      const response = await apiClient.patch(
        `/api/v1/system/legal-entities/${id}/`,
        data
      );
      return (response as any).data ?? response;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['legal-entities', variables.id] });
      queryClient.invalidateQueries({ queryKey: ['legal-entities'] });
    },
  });
}
