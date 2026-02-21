import { useAuth } from '@/lib/auth-context';

export function useCalendlyConfig() {
  const { user } = useAuth();
  
  const calendlyUrl = (user as any)?.practitioner_data?.calendly_url || null;
  const isConfigured = Boolean(calendlyUrl);
  
  return {
    calendlyUrl,
    isConfigured,
  };
}
