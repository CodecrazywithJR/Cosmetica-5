/**
 * Agenda Page (Opción B - Management Layer)
 * Main appointment list view - ERP internal agenda
 * Fully internationalized with next-intl
 * 
 * Purpose: Internal ERP agenda for managing existing appointments.
 * This is the MANAGEMENT layer, not the booking layer.
 * 
 * Flow: View appointments → Filter by date/status → Update status → Manage daily schedule
 * 
 * Architecture (Opción B):
 * - Calendly = Booking engine (creates appointments via webhook)
 * - Appointment model = Internal agenda (single source of truth for ERP)
 * - /agenda (this page) = Manage appointments
 * - /schedule = Create new appointments (Calendly embed)
 * 
 * Features:
 * - Lists appointments from Appointment model
 * - Filters by date and status
 * - Status transitions: scheduled → confirmed → checked_in → completed
 * - CTA "New Appointment" navigates to /schedule (Calendly booking)
 * 
 * This is the reference module for UX patterns across the ERP.
 * See docs/UX_PATTERNS.md for replication guidelines.
 * See docs/PROJECT_DECISIONS.md §12.28 (Opción B architecture)
 */

'use client';

import AppLayout from '@/components/layout/app-layout';
import { DataState } from '@/components/data-state';
import { useAppointments, useUpdateAppointmentStatus } from '@/lib/hooks/use-appointments';
import { useState, useMemo, useEffect, useRef } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter, useSearchParams } from 'next/navigation';
import { Appointment } from '@/lib/types';

/**
 * Helper: Get today's date in YYYY-MM-DD format
 */
function getTodayString(): string {
  return new Date().toISOString().split('T')[0];
}

/**
 * Helper: Validate and normalize date string
 * Returns null if invalid, otherwise returns normalized YYYY-MM-DD
 */
function validateDateString(dateStr: string | null): string | null {
  if (!dateStr) return null;
  const parsed = new Date(dateStr + 'T00:00:00'); // Force midnight to avoid timezone issues
  if (isNaN(parsed.getTime())) return null;
  return dateStr; // Already in YYYY-MM-DD format from URL
}

/**
 * Helper: Add days to a date string (YYYY-MM-DD)
 */
function addDays(dateStr: string, days: number): string {
  const date = new Date(dateStr + 'T00:00:00');
  date.setDate(date.getDate() + days);
  return date.toISOString().split('T')[0];
}

export default function AgendaPage() {
  const t = useTranslations('agenda');
  const tCommon = useTranslations('common');
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Single source of truth: Initialize state ONCE from URL, never re-sync from URL
  const initializedFromUrl = useRef(false);
  const [selectedDate, setSelectedDate] = useState(() => {
    const dateFromUrl = searchParams.get('date');
    initializedFromUrl.current = true;
    return validateDateString(dateFromUrl) || getTodayString();
  });
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get('status') || '');

  // Sync URL with state (without full page reload)
  // Guard: only update URL if it actually changed to prevent unnecessary re-renders
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedDate !== getTodayString()) {
      params.set('date', selectedDate);
    }
    if (statusFilter) {
      params.set('status', statusFilter);
    }
    const queryString = params.toString();
    const newUrl = queryString ? `?${queryString}` : `/${locale}`;
    
    // Guard: only replace if URL is different from current
    // Check if running in browser (not SSR)
    if (typeof window !== 'undefined') {
      const currentPath = window.location.pathname + window.location.search;
      const targetPath = `/${locale}` + (queryString ? `?${queryString}` : '');
      if (currentPath !== targetPath) {
        router.replace(newUrl, { scroll: false });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDate, statusFilter, locale]);

  const { data, isLoading, error } = useAppointments({
    date_from: selectedDate,
    date_to: selectedDate,
    status: statusFilter || undefined,
  });

  const updateStatus = useUpdateAppointmentStatus();

  // Appointments from API - no mock data
  const appointments = useMemo(() => {
    return data?.results || [];
  }, [data]);

  const isEmpty = appointments.length === 0;

  const handleStatusChange = (id: string, status: Appointment['status']) => {
    updateStatus.mutate({ id, status });
  };

  // Date formatter using current language
  const dateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      }),
    [locale]
  );

  // Time formatter using current language
  const timeFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        hour: '2-digit',
        minute: '2-digit',
      }),
    [locale]
  );

  return (
    <AppLayout>
      <div>
        {/* Page Header */}
        <div className="page-header">
          <div>
            <h1>{t('title')}</h1>
            <p className="page-description">{t('description')}</p>
          </div>
          <button
            onClick={() => router.push(`/${locale}/schedule`)}
            className="btn-primary"
            style={{ whiteSpace: 'nowrap' }}
          >
            {t('actions.newAppointment')}
          </button>
        </div>

        {/* Filters */}
        <div className="card" style={{ marginBottom: '16px', padding: '12px' }}>
          <div className="flex gap-2" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Date Navigation */}
            <div className="flex gap-2" style={{ alignItems: 'center' }}>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  setSelectedDate(prev => addDays(prev, -1));
                }}
                className="btn-secondary btn-sm"
                aria-label={t('filters.previousDay') || 'Previous day'}
                title={t('filters.previousDay') || 'Previous day'}
                type="button"
              >
                ←
              </button>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => {
                  const newDate = validateDateString(e.target.value);
                  if (newDate && newDate !== selectedDate) {
                    setSelectedDate(newDate);
                  }
                }}
                className="form-group"
                style={{ marginBottom: 0, width: 'auto', padding: '8px 12px', minWidth: '160px' }}
                aria-label={t('filters.date')}
              />
              <button
                onClick={(e) => {
                  e.preventDefault();
                  setSelectedDate(prev => addDays(prev, 1));
                }}
                className="btn-secondary btn-sm"
                aria-label={t('filters.nextDay') || 'Next day'}
                title={t('filters.nextDay') || 'Next day'}
                type="button"
              >
                →
              </button>
              {selectedDate !== getTodayString() && (
                <button
                  onClick={() => setSelectedDate(getTodayString())}
                  className="btn-secondary btn-sm"
                  style={{ fontSize: '13px' }}
                >
                  {t('filters.today') || 'Today'}
                </button>
              )}
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '8px 12px',
                border: '1px solid var(--gray-300)',
                borderRadius: '6px',
              }}
              aria-label={t('filters.status')}
            >
              <option value="">{t('filters.allStatuses')}</option>
              <option value="scheduled">{t('appointment.status.scheduled')}</option>
              <option value="confirmed">{t('appointment.status.confirmed')}</option>
              <option value="checked_in">{t('appointment.status.checked_in')}</option>
              <option value="completed">{t('appointment.status.completed')}</option>
              <option value="cancelled">{t('appointment.status.cancelled')}</option>
              <option value="no_show">{t('appointment.status.no_show')}</option>
            </select>
          </div>
        </div>

        {/* Data State Management */}
        <DataState
          isLoading={isLoading}
          error={error}
          isEmpty={isEmpty}
          emptyMessage={t('emptyState.title')}
          emptyDescription={t('emptyState.description')}
          emptyAction={{
            label: t('emptyState.action'),
            onClick: undefined, // No functionality yet - will be implemented later
          }}
          loadingMessage={tCommon('loading')}
          errorTitle={t('errors.title')}
          errorDescription={t('errors.description')}
        >
          {/* Success State - Data Table */}
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>{t('table.time')}</th>
                  <th>{t('table.patient')}</th>
                  <th>{t('table.practitioner')}</th>
                  <th>{t('table.type')}</th>
                  <th>{t('table.status')}</th>
                  <th>{t('table.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((apt) => (
                  <tr key={apt.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {timeFormatter.format(new Date(apt.scheduled_start))}
                      </div>
                      {apt.scheduled_end && (
                        <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                          {timeFormatter.format(new Date(apt.scheduled_end))}
                        </div>
                      )}
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{apt.patient.full_name}</div>
                      <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                        {apt.patient.email || apt.patient.phone || '—'}
                      </div>
                    </td>
                    <td>{apt.practitioner?.display_name || '—'}</td>
                    <td>
                      <span style={{ fontSize: '13px', color: 'var(--gray-700)' }}>
                        {apt.source}
                      </span>
                    </td>
                    <td>
                      <span className={`badge badge-${apt.status}`}>
                        {t(`appointment.status.${apt.status}`)}
                      </span>
                    </td>
                    <td>
                      <div className="flex gap-2">
                        {apt.status === 'scheduled' && (
                          <button
                            onClick={() => handleStatusChange(apt.id, 'confirmed')}
                            className="btn-secondary btn-sm"
                            disabled={updateStatus.isPending}
                          >
                            {t('actions.confirm')}
                          </button>
                        )}
                        {apt.status === 'confirmed' && (
                          <button
                            onClick={() => handleStatusChange(apt.id, 'checked_in')}
                            className="btn-primary btn-sm"
                            disabled={updateStatus.isPending}
                          >
                            {t('actions.checkIn')}
                          </button>
                        )}
                        {apt.status === 'checked_in' && (
                          <button
                            onClick={() => handleStatusChange(apt.id, 'completed')}
                            className="btn-primary btn-sm"
                            disabled={updateStatus.isPending}
                          >
                            {t('actions.complete')}
                          </button>
                        )}
                        {(apt.status === 'scheduled' || apt.status === 'confirmed') && (
                          <button
                            onClick={() => handleStatusChange(apt.id, 'cancelled')}
                            className="btn-secondary btn-sm"
                            disabled={updateStatus.isPending}
                            style={{ color: 'var(--error)' }}
                          >
                            {t('actions.cancel')}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Summary Footer */}
          {appointments.length > 0 && (
            <div style={{ marginTop: '16px', fontSize: '14px', color: 'var(--gray-600)' }}>
              {t('summary.totalAppointments')}: {appointments.length}
            </div>
          )}
        </DataState>
      </div>
    </AppLayout>
  );
}
