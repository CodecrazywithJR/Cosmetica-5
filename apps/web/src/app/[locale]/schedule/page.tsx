/**
 * Schedule Page - FASE 4.1 (Opción B)
 * 
 * Purpose: Calendly booking interface for creating new appointments.
 * This is the BOOKING layer, not the management layer.
 * 
 * Flow: Patient/Staff books via Calendly → Webhook → Appointment created → Appears in Agenda
 * 
 * Behavior:
 * - If practitioner has calendly_url configured → shows CalendlyEmbed widget
 * - If calendly_url is null/empty → shows CalendlyNotConfigured message
 * 
 * Architecture (Opción B):
 * - Calendly = Booking engine (single source for scheduling)
 * - Appointment = Internal agenda (ERP management)
 * - /schedule = Create appointments (this page)
 * - /agenda (/) = Manage appointments (list, filters, status updates)
 * 
 * Technical:
 * - Uses useCalendlyConfig() hook (practitioner.calendly_url → fallback to env var)
 * - CalendlyEmbed wraps react-calendly InlineWidget
 * - Fail-safe: Component returns null if URL is invalid
 * 
 * See: docs/PROJECT_DECISIONS.md §12.28 (Opción B - Calendly + Agenda interna)
 */

'use client';

import AppLayout from '@/components/layout/app-layout';
import { CalendlyEmbed } from '@/components/calendly-embed';
import { CalendlyNotConfigured } from '@/components/calendly-not-configured';
import { useCalendlyConfig } from '@/lib/hooks/use-calendly-config';
import { useTranslations } from 'next-intl';

export default function SchedulePage() {
  const t = useTranslations('schedule');
  const { calendlyUrl, isConfigured } = useCalendlyConfig();

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('title')}</h1>
          <p className="page-description">{t('description')}</p>
        </div>
      </div>

      <div className="page-content">
        {isConfigured && calendlyUrl ? (
          <CalendlyEmbed url={calendlyUrl} />
        ) : (
          <CalendlyNotConfigured />
        )}
      </div>
    </AppLayout>
  );
}
