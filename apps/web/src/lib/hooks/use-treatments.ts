/**
 * Treatments hooks - Fetch treatment catalog
 */

import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

export interface Treatment {
  id: string; // UUID
  name: string;
  description?: string;
  default_price: string; // Decimal as string
  is_active: boolean;
  requires_stock: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Fetch active treatments from the catalog.
 * Used in encounter detail to populate treatment selector.
 */
export function useTreatments() {
  return useQuery({
    queryKey: ['treatments'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/clinical/treatments/');
      return (response as any).data?.results || (response as any).data || [];
    },
    staleTime: 5 * 60 * 1000, // 5 min — catalog doesn't change often
  });
}
