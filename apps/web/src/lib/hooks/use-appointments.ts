import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

interface Patient {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email?: string;
  phone?: string;
}

interface Practitioner {
  id: string;
  display_name: string;
}

export interface Appointment {
  id: string;
  patient_id: string;
  patient: Patient;
  patient_name: string;
  practitioner_id?: string;
  practitioner?: Practitioner;
  practitioner_name?: string;
  location_id?: string;
  location_name?: string;
  source: string;
  status: 'scheduled' | 'confirmed' | 'checked_in' | 'completed' | 'cancelled' | 'no_show';
  scheduled_start: string;
  scheduled_end: string;
  notes?: string;
  cancellation_reason?: string;
  no_show_reason?: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

interface AppointmentsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Appointment[];
}

interface AppointmentsParams {
  date_from?: string;
  date_to?: string;
  status?: string;
  patient_id?: string;
  practitioner_id?: string;
  location_id?: string;
}

export function useAppointments(params?: AppointmentsParams) {
  return useQuery<AppointmentsResponse>({
    queryKey: ['appointments', params],
    queryFn: async () => {
      const queryParams = new URLSearchParams();
      
      if (params?.date_from) queryParams.append('date_from', params.date_from);
      if (params?.date_to) queryParams.append('date_to', params.date_to);
      if (params?.status) queryParams.append('status', params.status);
      if (params?.patient_id) queryParams.append('patient_id', params.patient_id);
      if (params?.practitioner_id) queryParams.append('practitioner_id', params.practitioner_id);
      if (params?.location_id) queryParams.append('location_id', params.location_id);
      
      const url = `/api/v1/clinical/appointments/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
      return apiClient.get<AppointmentsResponse>(url);
    },
  });
}

export function useUpdateAppointmentStatus() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, status, reason }: { id: string; status: Appointment['status']; reason?: string }) => {
      return apiClient.post(`/api/v1/clinical/appointments/${id}/transition/`, { status, reason });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
    },
  });
}
