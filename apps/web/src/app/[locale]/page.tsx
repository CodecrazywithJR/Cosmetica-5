/**
 * Agenda Page
 * Main calendar/list view of appointments (FIRST SCREEN)
 * Fully internationalized with next-intl
 * 
 * This is the reference module for UX patterns across the ERP.
 * See docs/UX_PATTERNS.md for replication guidelines.
 */

'use client';

import AppLayout from '@/components/layout/app-layout';
import { DataState } from '@/components/data-state';
import { useAppointments, useUpdateAppointmentStatus } from '@/lib/hooks/use-appointments';
import { useState, useMemo } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { Appointment } from '@/lib/types';
import { ENABLE_MOCK_DATA, getMockAppointments } from '@/lib/mock/agenda-mock';

export default function AgendaPage() {
  const t = useTranslations('agenda');
  const tCommon = useTranslations('common');
  const locale = useLocale();
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [statusFilter, setStatusFilter] = useState<string>('');

  const { data, isLoading, error } = useAppointments({
    date: selectedDate,
    status: statusFilter || undefined,
  });

  const updateStatus = useUpdateAppointmentStatus();

  // DEV-ONLY: Use mock data when backend returns empty array
  // This allows visual verification of the layout without real data
  // TODO: Remove this when backend provides real data
  const appointments = useMemo(() => {
    if (error || isLoading) return data?.results || [];
    const realData = data?.results || [];
    if (realData.length === 0 && ENABLE_MOCK_DATA) {
      return getMockAppointments(selectedDate);
    }
    return realData;
  }, [data, error, isLoading, selectedDate]);

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
          <h1>{t('title')}</h1>
          <div className="flex gap-2">
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="form-group"
              style={{ marginBottom: 0, width: 'auto', padding: '8px 12px' }}
              aria-label={t('filters.date')}
            />
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
