/**
 * API Routes Configuration
 * IMPORTANT: These are the ACTUAL backend routes verified from Django
 */

export const API_ROUTES = {
  AUTH: {
    LOGIN: '/api/auth/token/',  // JWT token endpoint
    LOGOUT: '/api/auth/logout/',
    ME: '/api/auth/me/',  // Current user profile
  },
  USERS: {
    LIST: '/api/v1/users/',
    DETAIL: (id: number) => `/api/v1/users/${id}/`,
    RESET_PASSWORD: (id: number) => `/api/v1/users/${id}/reset-password/`,
    CHANGE_PASSWORD_SELF: '/api/v1/users/change-password/',
  },
  CLINICAL: {
    PATIENTS: '/api/v1/clinical/patients/',
    PATIENT_DETAIL: (id: number) => `/api/v1/clinical/patients/${id}/`,
    APPOINTMENTS: '/api/v1/clinical/appointments/',
    ENCOUNTERS: '/api/v1/clinical/encounters/',
    ENCOUNTER_DETAIL: (id: number) => `/api/v1/clinical/encounters/${id}/`,
  },
  PRACTITIONERS: {
    LIST: '/api/v1/practitioners/',
    DETAIL: (id: string) => `/api/v1/practitioners/${id}/`,
    AVAILABILITY: (id: string) => `/api/v1/clinical/practitioners/${id}/availability/`,
    CALENDAR: (id: string) => `/api/v1/clinical/practitioners/${id}/calendar/`,
    // BOOK endpoint REMOVED (PHASE 2 - AGENDA_SURGERY.md)
    // Reason: Backend endpoint deleted in PHASE 1, creates source='manual' appointments
  },
};
