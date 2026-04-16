/**
 * Proposals hooks
 */

import { useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

/** Paginated response shape matching backend DRF pagination */
interface PaginatedProposals {
  count: number;
  next: string | null;
  previous: string | null;
  results: any[];
}

/**
 * Fetch list of proposals with optional status filter.
 * Calls GET /api/v1/clinical/proposals/
 */
export function useProposals(params?: { status?: string }) {
  return useQuery({
    queryKey: ['proposals', params?.status],
    queryFn: async () => {
      const queryParams = params?.status ? `?status=${params.status}` : '';
      const response = await apiClient.get(`/api/v1/clinical/proposals/${queryParams}`);
      return ((response as any).data || response) as PaginatedProposals;
    },
  });
}

/**
 * Fetch a single proposal by ID (detail view).
 * GET /api/v1/clinical/proposals/{id}/
 */
export function useProposal(id: string) {
  return useQuery({
    queryKey: ['proposals', id],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/clinical/proposals/${id}/`);
      return (response as any).data || response;
    },
    enabled: !!id,
  });
}

/**
 * Send a proposal (draft → sent).
 * POST /api/v1/clinical/proposals/{id}/send/
 */
export function useSendProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { id: string }) => {
      const response = await apiClient.post(
        `/api/v1/clinical/proposals/${payload.id}/send/`,
        {}
      );
      return (response as any).data || response;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposals', variables.id] });
    },
  });
}

/**
 * Accept a proposal (sent → accepted). Creates Sale + TreatmentPlans.
 * POST /api/v1/clinical/proposals/{id}/accept/
 */
export function useAcceptProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { id: string; legalEntityId: string }) => {
      const response = await apiClient.post(
        `/api/v1/clinical/proposals/${payload.id}/accept/`,
        { legal_entity_id: payload.legalEntityId }
      );
      return (response as any).data || response;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposals', variables.id] });
    },
  });
}

/**
 * Mutation for converting a proposal to sale.
 * TODO: Wire to real sales endpoint when sales module is ready.
 */
export function useConvertProposalToSale() {
  const [isPending, setIsPending] = useState(false);
  const mutateAsync = useCallback(async (_payload: { proposalId: string; legalEntityId: string }) => {
    setIsPending(true);
    try {
      console.warn('[stub] useConvertProposalToSale — sales module not yet implemented');
    } finally {
      setIsPending(false);
    }
  }, []);
  return { mutateAsync, isPending };
}

/**
 * Cancel a proposal via API.
 * POST /api/v1/clinical/proposals/{id}/cancel/
 */
export function useCancelProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { id: string; cancellationReason: string }) => {
      const response = await apiClient.post(
        `/api/v1/clinical/proposals/${payload.id}/cancel/`,
        { cancellation_reason: payload.cancellationReason }
      );
      return (response as any).data || response;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['proposals', variables.id] });
    },
  });
}

/**
 * Generate a proposal from a finalized encounter.
 * POST /api/v1/clinical/encounters/{id}/generate-proposal/
 */
export function useGenerateProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { encounterId: string }): Promise<{ proposal_id: string; total_amount: string; line_count: number; status: string }> => {
      const response = await apiClient.post(
        `/api/v1/clinical/encounters/${payload.encounterId}/generate-proposal/`,
        {}
      );
      return (response as any).data || response;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      queryClient.invalidateQueries({ queryKey: ['encounters'] });
    },
  });
}
