/**
 * Attachments hooks - For photos and documents
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

export function useUploadPhoto() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ encounterId, file, category }: { encounterId: string; file: File; category: string }) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('classification', category);

      const response = await apiClient.post(
        `/api/v1/clinical/encounters/${encounterId}/photos/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      const uploadUrl = (response as any).data.upload_url;
      await fetch(uploadUrl, {
        method: 'PUT',
        headers: {
          'Content-Type': file.type,
        },
        body: file,
      });

      return (response as any).data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['encounters', variables.encounterId] });
    },
  });
}

export function useDeletePhoto() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (photoId: string) => {
      await apiClient.delete(`/api/v1/clinical/photos/${photoId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['encounters'] });
    },
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ encounterId, file }: { encounterId: string; file: File }) => {
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiClient.post(
        `/api/v1/clinical/encounters/${encounterId}/documents/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return (response as any).data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['encounters', variables.encounterId] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      await apiClient.delete(`/api/v1/clinical/documents/${documentId}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['encounters'] });
    },
  });
}
