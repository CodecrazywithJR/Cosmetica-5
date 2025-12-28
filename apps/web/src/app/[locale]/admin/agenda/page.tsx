/**
 * Agenda Page - Calendar View (Sprint 1: Read-Only)
 * Shows practitioner appointments and blocks in calendar format
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useAuth, ROLES } from '@/lib/auth-context';
import AppLayout from '@/components/layout/app-layout';
import Unauthorized from '@/components/unauthorized';
import apiClient from '@/lib/api-client';
import { format, startOfWeek, addDays, addWeeks, subWeeks, parseISO } from 'date-fns';
import { es } from 'date-fns/locale';

interface CalendarEvent {
  id: string;
  type: 'appointment' | 'block';
  title: string;
  start: string;
  end: string;
  practitioner_id: string;
  practitioner_name: string;
  patient_id?: string | null;
  patient_name?: string | null;
  appointment_status?: string | null;
  appointment_source?: string | null;
  block_kind?: string | null;
  notes?: string | null;
}

interface Practitioner {
  id: string;
  user: {
    first_name: string;
    last_name: string;
    full_name: string;
  };
}

export default function AgendaPage() {
  const { hasRole, isLoading: authLoading, user } = useAuth();
  const t = useTranslations('common');
  const locale = useLocale();

  const [practitioners, setPractitioners] = useState<Practitioner[]>([]);
  const [selectedPractitionerId, setSelectedPractitionerId] = useState<string>('');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(startOfWeek(new Date(), { weekStartsOn: 1 }));

  // Check authorization
  const isAdmin = hasRole(ROLES.ADMIN);
  const isReception = hasRole(ROLES.RECEPTION);
  const isPractitioner = hasRole(ROLES.PRACTITIONER);
  const canViewAgenda = isAdmin || isReception || isPractitioner;

  useEffect(() => {
    if (!authLoading && canViewAgenda) {
      loadPractitioners();
    }
  }, [authLoading, canViewAgenda]);

  useEffect(() => {
    if (selectedPractitionerId) {
      loadCalendarEvents();
    }
  }, [selectedPractitionerId, currentWeekStart]);

  const loadPractitioners = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Fetch practitioners list
      const response = await apiClient.get('/api/v1/practitioners/');
      const practitionersData = Array.isArray(response.data) ? response.data : response.data?.results || [];
      setPractitioners(practitionersData);

      // Auto-select practitioner
      if (practitionersData.length > 0) {
        // If practitioner role, select their own ID
        if (isPractitioner && !isAdmin && !isReception) {
          // Find practitioner by user ID (since we don't have email in the user object)
          // For simplicity, just select the first one for now
          // TODO: Implement proper practitioner-user matching
          setSelectedPractitionerId(practitionersData[0].id);
        } else {
          // Admin or Reception: select first practitioner
          setSelectedPractitionerId(practitionersData[0].id);
        }
      }
    } catch (err: any) {
      console.error('Failed to load practitioners:', err);
      setError(err.response?.data?.detail || 'Error loading practitioners');
    } finally {
      setIsLoading(false);
    }
  };

  const loadCalendarEvents = async () => {
    if (!selectedPractitionerId) return;

    try {
      setIsLoading(true);
      setError(null);

      // Calculate date range (7 days from currentWeekStart)
      const dateFrom = format(currentWeekStart, 'yyyy-MM-dd');
      const dateTo = format(addDays(currentWeekStart, 6), 'yyyy-MM-dd');

      const response = await apiClient.get(
        `/api/v1/clinical/practitioners/${selectedPractitionerId}/calendar/`,
        {
          params: { date_from: dateFrom, date_to: dateTo },
        }
      );

      setEvents(response.data.events || []);
    } catch (err: any) {
      console.error('Failed to load calendar events:', err);
      setError(err.response?.data?.error || 'Error loading calendar');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePreviousWeek = () => {
    setCurrentWeekStart(subWeeks(currentWeekStart, 1));
  };

  const handleNextWeek = () => {
    setCurrentWeekStart(addWeeks(currentWeekStart, 1));
  };

  const handleToday = () => {
    setCurrentWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 }));
  };

  // Wait for auth to load
  if (authLoading) {
    return (
      <AppLayout>
        <div className="loading-container">
          <p>{t('loading')}</p>
        </div>
      </AppLayout>
    );
  }

  // Show 403 if not authorized
  if (!canViewAgenda) {
    return <Unauthorized />;
  }

  // Group events by day
  const eventsByDay: Record<string, CalendarEvent[]> = {};
  for (let i = 0; i < 7; i++) {
    const dayDate = addDays(currentWeekStart, i);
    const dayKey = format(dayDate, 'yyyy-MM-dd');
    eventsByDay[dayKey] = events.filter((event) => {
      const eventDate = format(parseISO(event.start), 'yyyy-MM-dd');
      return eventDate === dayKey;
    });
  }

  return (
    <AppLayout>
      <div className="agenda-page" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '24px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px' }}>
            📅 Agenda
          </h1>
          <p style={{ color: '#666' }}>
            Vista semanal de citas y bloqueos del practitioner
          </p>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex',
          gap: '16px',
          marginBottom: '24px',
          alignItems: 'center',
          flexWrap: 'wrap'
        }}>
          {/* Practitioner Selector */}
          {(isAdmin || isReception) && (
            <div style={{ flex: '1', minWidth: '200px' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                Practitioner
              </label>
              <select
                value={selectedPractitionerId}
                onChange={(e) => setSelectedPractitionerId(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid #ddd',
                  borderRadius: '6px',
                  fontSize: '14px'
                }}
              >
                <option value="">Seleccionar...</option>
                {practitioners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.user?.full_name || `${p.user?.first_name} ${p.user?.last_name}`}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Week Navigation */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              onClick={handlePreviousWeek}
              style={{
                padding: '8px 16px',
                border: '1px solid #ddd',
                borderRadius: '6px',
                background: 'white',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              ← Anterior
            </button>
            <button
              onClick={handleToday}
              style={{
                padding: '8px 16px',
                border: '1px solid #ddd',
                borderRadius: '6px',
                background: 'white',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              Hoy
            </button>
            <button
              onClick={handleNextWeek}
              style={{
                padding: '8px 16px',
                border: '1px solid #ddd',
                borderRadius: '6px',
                background: 'white',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Siguiente →
            </button>
          </div>
        </div>

        {/* Current Week Display */}
        <div style={{
          padding: '12px 16px',
          background: '#f8f9fa',
          borderRadius: '8px',
          marginBottom: '24px',
          textAlign: 'center',
          fontSize: '16px',
          fontWeight: '500'
        }}>
          {format(currentWeekStart, "d 'de' MMMM", { locale: es })} - {format(addDays(currentWeekStart, 6), "d 'de' MMMM 'de' yyyy", { locale: es })}
        </div>

        {/* Loading State */}
        {isLoading && (
          <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
            <p>Cargando eventos...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div style={{
            padding: '16px',
            background: '#fee',
            border: '1px solid #fcc',
            borderRadius: '8px',
            color: '#c00',
            marginBottom: '24px'
          }}>
            {error}
          </div>
        )}

        {/* Calendar Grid */}
        {!isLoading && !error && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '12px'
          }}>
            {[0, 1, 2, 3, 4, 5, 6].map((dayOffset) => {
              const dayDate = addDays(currentWeekStart, dayOffset);
              const dayKey = format(dayDate, 'yyyy-MM-dd');
              const dayEvents = eventsByDay[dayKey] || [];
              const isToday = format(new Date(), 'yyyy-MM-dd') === dayKey;

              return (
                <div
                  key={dayKey}
                  style={{
                    border: isToday ? '2px solid #4f46e5' : '1px solid #ddd',
                    borderRadius: '8px',
                    padding: '12px',
                    background: isToday ? '#f0f0ff' : 'white',
                    minHeight: '200px'
                  }}
                >
                  {/* Day Header */}
                  <div style={{ marginBottom: '12px', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
                    <div style={{ fontSize: '12px', color: '#666', textTransform: 'uppercase', fontWeight: '600' }}>
                      {format(dayDate, 'EEEE', { locale: es })}
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: isToday ? '#4f46e5' : '#111' }}>
                      {format(dayDate, 'd')}
                    </div>
                  </div>

                  {/* Events */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {dayEvents.length === 0 && (
                      <div style={{ padding: '16px', textAlign: 'center', color: '#999', fontSize: '12px' }}>
                        Sin eventos
                      </div>
                    )}
                    {dayEvents.map((event) => (
                      <div
                        key={event.id}
                        style={{
                          padding: '8px',
                          borderRadius: '6px',
                          background: event.type === 'appointment'
                            ? event.appointment_status === 'confirmed' ? '#dcfce7' : '#fef3c7'
                            : '#e0e7ff',
                          border: '1px solid',
                          borderColor: event.type === 'appointment'
                            ? event.appointment_status === 'confirmed' ? '#86efac' : '#fde047'
                            : '#c7d2fe',
                          fontSize: '12px'
                        }}
                      >
                        <div style={{ fontWeight: '600', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          {event.type === 'appointment' ? '📅' : '🚫'}
                          {format(parseISO(event.start), 'HH:mm')}
                        </div>
                        <div style={{ color: '#444' }}>
                          {event.title}
                        </div>
                        {event.patient_name && (
                          <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>
                            {event.patient_name}
                          </div>
                        )}
                        {event.block_kind && (
                          <div style={{ fontSize: '11px', color: '#666', marginTop: '4px', textTransform: 'capitalize' }}>
                            {event.block_kind}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
