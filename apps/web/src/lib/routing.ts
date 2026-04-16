/**
 * Routing utilities - Locale-aware navigation
 * Respects existing next-intl setup with [locale] routes
 */

export type Locale = 'en' | 'ru' | 'fr' | 'uk' | 'hy' | 'es';

/**
 * Application routes with locale support
 */
export const routes = {
  home: (locale: Locale) => `/${locale}`,
  login: (locale: Locale) => `/${locale}/login`,
  dashboard: (locale: Locale) => `/${locale}`,  // Dashboard = home
  
  // Agenda/Appointments
  agenda: (locale: Locale) => `/${locale}`,
  schedule: (locale: Locale) => `/${locale}/schedule`,  // Booking page
  
  // Patients - nested structure
  patients: {
    list: (locale: Locale) => `/${locale}/patients`,
    detail: (locale: Locale, id: string) => `/${locale}/patients/${id}`,
    edit: (locale: Locale, id: string) => `/${locale}/patients/${id}/edit`,
    create: (locale: Locale) => `/${locale}/patients/new`,
  },
  
  // Legacy flat patient routes (for backwards compatibility)
  patientDetail: (locale: Locale, id: string) => `/${locale}/patients/${id}`,
  patientEdit: (locale: Locale, id: string) => `/${locale}/patients/${id}/edit`,
  patientNew: (locale: Locale) => `/${locale}/patients/new`,
  
  // Encounters - nested structure
  encounters: {
    list: (locale: Locale) => `/${locale}/encounters`,
    detail: (locale: Locale, id: string) => `/${locale}/encounters/${id}`,
  },
  
  // Legacy flat encounter routes
  encounterDetail: (locale: Locale, id: string) => `/${locale}/encounters/${id}`,
  
  // Treatment Sessions - clinical workspace
  treatmentSessions: {
    detail: (locale: Locale, id: string) => `/${locale}/clinical/treatment-sessions/${id}`,
  },

  // Legal Entities - admin management
  legalEntities: {
    list: (locale: Locale) => `/${locale}/admin/legal-entities`,
    create: (locale: Locale) => `/${locale}/admin/legal-entities/new`,
    detail: (locale: Locale, id: string) => `/${locale}/admin/legal-entities/${id}`,
    edit: (locale: Locale, id: string) => `/${locale}/admin/legal-entities/${id}/edit`,
  },

  // Proposals - nested structure
  proposals: {
    list: (locale: Locale) => `/${locale}/proposals`,
    detail: (locale: Locale, id: string) => `/${locale}/proposals/${id}`,
  },
  
  // Admin - base route
  admin: (locale: Locale) => `/${locale}/admin/users`,  // Default to users
  
  // Admin users - nested structure
  adminUsers: (locale: Locale) => `/${locale}/admin/users`,
  adminUserDetail: (locale: Locale, id: number) => `/${locale}/admin/users/${id}`,
  adminUserEdit: (locale: Locale, id: number) => `/${locale}/admin/users/${id}/edit`,
  adminUserNew: (locale: Locale) => `/${locale}/admin/users/new`,
  adminAgenda: (locale: Locale) => `/${locale}/admin/agenda`,
  
  // Booking route (native booking system)
  booking: (locale: Locale) => `/${locale}/booking`,
  
  // Users - nested structure (used by admin pages)
  users: {
    list: (locale: Locale) => `/${locale}/admin/users`,
    create: (locale: Locale) => `/${locale}/admin/users/new`,
    edit: (locale: Locale, id: number | string) => `/${locale}/admin/users/${id}/edit`,
    detail: (locale: Locale, id: number | string) => `/${locale}/admin/users/${id}`,
  },
  
  // Sales - FUTURE MODULE (stub to prevent crashes)
  // TODO: Implement sales module pages when ready
  sales: {
    list: (locale: Locale) => `/${locale}`,  // Redirect to home for now
    detail: (locale: Locale, id: number | string) => `/${locale}`,
    create: (locale: Locale) => `/${locale}`,
  },
  
  // Clinic Settings - Administrative parameters
  clinicSettings: (locale: Locale) => `/${locale}/clinic-settings`,
  
  // Auth
  mustChangePassword: (locale: Locale) => `/${locale}/must-change-password`,
};
