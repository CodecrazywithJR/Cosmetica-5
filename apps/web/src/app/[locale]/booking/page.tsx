/**
 * Booking Page
 * 
 * Sprint 4: UX Booking desde Availability
 * 
 * Native appointment booking system (no Calendly).
 * 
 * Features:
 * - RBAC: Admin/Reception can select any practitioner, Practitioner sees own calendar only
 * - Date range selector (defaults to next 7 days)
 * - Availability calendar with slots filtered by date/time
 * - Booking modal for confirming appointment
 * - Automatic refresh after successful booking
 * - Error handling for all backend validation rules
 * 
 * Backend integration:
 * - GET  /api/v1/clinical/practitioners/{id}/availability/
 * - POST /api/v1/clinical/practitioners/{id}/book/
 * 
 * Critical rule: Does NOT show slots where slot_start <= now
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import AppLayout from '@/components/layout/app-layout';
import { AvailabilityCalendar } from '@/components/booking/availability-calendar';
import { BookingModal } from '@/components/booking/booking-modal';
import {
  fetchAvailability,
  fetchPractitioners,
  fetchPatients,
  fetchLocations,
  createBooking,
} from '@/lib/api/booking';
import type {
  DayAvailability,
  TimeSlot,
  PractitionerInfo,
  PatientInfo,
  LocationInfo,
} from '@/lib/types/booking';

// Diagnostic panel state interface
interface DiagnosticInfo {
  practitionerId: string | null;
  role: string | null;
  dateFrom: string | null;
  dateTo: string | null;
  lastRequestUrl: string | null;
  lastStatusCode: number | null;
  lastErrorMessage: string | null;
  lastResponseBody: any;
  timestamp: number | null;
  timezone: string;
}

export default function BookingPage() {
  const { user, hasAnyRole } = useAuth();
  
  // Access control
  const isAdmin = hasAnyRole(['Admin']);
  const isReception = hasAnyRole(['Reception']);
  const isPractitioner = hasAnyRole(['Practitioner']);
  const canSelectPractitioner = isAdmin || isReception;

  // Data state
  const [practitioners, setPractitioners] = useState<PractitionerInfo[]>([]);
  const [patients, setPatients] = useState<PatientInfo[]>([]);
  const [locations, setLocations] = useState<LocationInfo[]>([]);
  const [availability, setAvailability] = useState<DayAvailability[]>([]);

  // Selection state
  const [selectedPractitioner, setSelectedPractitioner] = useState<string>('');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // UI state
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [loadingData, setLoadingData] = useState(true);
  const [error, setError] = useState<string>('');
  const [showModal, setShowModal] = useState(false);

  // Diagnostic state (development only)
  const [diagnostic, setDiagnostic] = useState<DiagnosticInfo>({
    practitionerId: null,
    role: null,
    dateFrom: null,
    dateTo: null,
    lastRequestUrl: null,
    lastStatusCode: null,
    lastErrorMessage: null,
    lastResponseBody: null,
    timestamp: null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });

  const isDevelopment = process.env.NODE_ENV === 'development';

  // Helper: Get today's date as YYYY-MM-DD
  const getTodayString = (): string => {
    const today = new Date();
    return formatDateForInput(today);
  };

  // Helper: Get date N days from today
  const getDaysFromToday = (days: number): string => {
    const date = new Date();
    date.setDate(date.getDate() + days);
    return formatDateForInput(date);
  };

  // Initialize date range (today + 7 days) - FIX for 2025/2026 bug
  useEffect(() => {
    const today = getTodayString();
    const nextWeek = getDaysFromToday(7);
    
    setDateFrom(today);
    setDateTo(nextWeek);
    
    // Update diagnostic
    setDiagnostic(prev => ({
      ...prev,
      dateFrom: today,
      dateTo: nextWeek,
    }));
  }, []);

  // Load initial data
  useEffect(() => {
    loadInitialData();
  }, []);

  // Auto-load availability when practitioner or date range changes
  useEffect(() => {
    if (selectedPractitioner && dateFrom && dateTo) {
      loadAvailability();
    }
  }, [selectedPractitioner, dateFrom, dateTo]);

  const loadInitialData = async () => {
    try {
      setLoadingData(true);
      setError('');

      const [practitionersData, patientsData, locationsData] = await Promise.all([
        fetchPractitioners(),
        fetchPatients(),
        fetchLocations(),
      ]);

      setPractitioners(practitionersData);
      setPatients(patientsData);
      setLocations(locationsData);

      // Determine user role for diagnostic
      const userRole = isAdmin ? 'Admin' : isReception ? 'Reception' : isPractitioner ? 'Practitioner' : 'Unknown';
      
      // Auto-select practitioner
      if (practitionersData.length > 0) {
        let selectedId = '';
        
        // If practitioner role, try to find own practitioner
        if (isPractitioner && user) {
          const ownPractitioner = practitionersData.find(
            p => p.id === user.id
          );
          selectedId = ownPractitioner?.id || practitionersData[0].id;
        } else {
          selectedId = practitionersData[0].id;
        }
        
        setSelectedPractitioner(selectedId);
        
        // Update diagnostic
        setDiagnostic(prev => ({
          ...prev,
          practitionerId: selectedId,
          role: userRole,
        }));
      } else {
        throw new Error('No practitioners found. Please contact administrator.');
      }
    } catch (err: any) {
      console.error('Failed to load initial data:', err);
      
      // Better error messages
      let errorMsg = 'Error al cargar datos iniciales.';
      let detailedError = err.message || 'Unknown error';
      
      if (err?.response) {
        const status = err.response.status;
        detailedError = `HTTP ${status}: ${err.response.data?.detail || err.response.statusText}`;
        
        if (status === 401) {
          errorMsg = 'No está autenticado. Por favor, inicie sesión nuevamente.';
        } else if (status === 403) {
          errorMsg = 'No tiene permisos para acceder a esta información.';
        } else if (status === 404) {
          errorMsg = 'Endpoint no encontrado. Verifique la configuración del servidor.';
        } else if (status >= 500) {
          errorMsg = 'Error del servidor. Intente más tarde.';
        }
      } else if (err?.request) {
        errorMsg = 'No se pudo conectar con el servidor. Verifique su conexión.';
        detailedError = 'Network error - no response from server';
      }
      
      setError(`${errorMsg} (${detailedError})`);
      
      // Update diagnostic
      setDiagnostic(prev => ({
        ...prev,
        lastStatusCode: err?.response?.status || null,
        lastErrorMessage: detailedError,
        lastResponseBody: err?.response?.data || null,
        timestamp: Date.now(),
      }));
    } finally {
      setLoadingData(false);
    }
  };

  const loadAvailability = async () => {
    if (!selectedPractitioner || !dateFrom || !dateTo) return;

    try {
      setLoadingAvailability(true);
      setError('');

      // Build the request URL for diagnostic
      const requestUrl = `/api/v1/clinical/practitioners/${selectedPractitioner}/availability/?date_from=${dateFrom}&date_to=${dateTo}&slot_duration=30`;
      
      // Update diagnostic before request
      setDiagnostic(prev => ({
        ...prev,
        lastRequestUrl: requestUrl,
        timestamp: Date.now(),
      }));

      const data = await fetchAvailability(
        selectedPractitioner,
        dateFrom,
        dateTo,
        30 // 30-minute slots
      );

      setAvailability(data.availability);
      
      // Update diagnostic on success
      setDiagnostic(prev => ({
        ...prev,
        lastStatusCode: 200,
        lastErrorMessage: null,
        lastResponseBody: { success: true, days: data.availability.length },
      }));
    } catch (err: any) {
      console.error('Failed to load availability:', err);
      
      // Better error messages
      let errorMsg = 'Error al cargar disponibilidad.';
      let detailedError = err.message || 'Unknown error';
      
      if (err?.response) {
        const status = err.response.status;
        const responseData = err.response.data;
        detailedError = `HTTP ${status}: ${responseData?.detail || err.response.statusText}`;
        
        if (status === 403) {
          errorMsg = 'No tiene permisos para ver la disponibilidad de este profesional.';
        } else if (status === 404) {
          errorMsg = 'Profesional no encontrado o endpoint incorrecto.';
        } else if (status === 400) {
          errorMsg = `Datos inválidos: ${responseData?.detail || 'Verifique las fechas'}`;
        } else if (status >= 500) {
          errorMsg = 'Error del servidor al obtener disponibilidad.';
        }
        
        // Update diagnostic
        setDiagnostic(prev => ({
          ...prev,
          lastStatusCode: status,
          lastErrorMessage: detailedError,
          lastResponseBody: responseData,
          timestamp: Date.now(),
        }));
      } else if (err?.request) {
        errorMsg = 'No se pudo conectar con el servidor.';
        detailedError = 'Network error';
        
        setDiagnostic(prev => ({
          ...prev,
          lastStatusCode: null,
          lastErrorMessage: detailedError,
          lastResponseBody: null,
          timestamp: Date.now(),
        }));
      }
      
      setError(`${errorMsg} ${detailedError}`);
      setAvailability([]);
    } finally {
      setLoadingAvailability(false);
    }
  };

  const handleSlotSelect = (date: string, slot: TimeSlot) => {
    setSelectedDate(date);
    setSelectedSlot(slot);
    setShowModal(true);
  };

  // Handle date change with validation
  const handleDateFromChange = (newDate: string) => {
    const today = getTodayString();
    
    // If date is too far in the past, reset to today
    if (newDate < '2020-01-01' || newDate > '2030-12-31') {
      setDateFrom(today);
      setDiagnostic(prev => ({ ...prev, dateFrom: today }));
    } else {
      setDateFrom(newDate);
      setDiagnostic(prev => ({ ...prev, dateFrom: newDate }));
    }
  };

  const handleDateToChange = (newDate: string) => {
    const today = getTodayString();
    
    // If date is too far in the past or future, reset to today + 7
    if (newDate < '2020-01-01' || newDate > '2030-12-31') {
      const nextWeek = getDaysFromToday(7);
      setDateTo(nextWeek);
      setDiagnostic(prev => ({ ...prev, dateTo: nextWeek }));
    } else {
      setDateTo(newDate);
      setDiagnostic(prev => ({ ...prev, dateTo: newDate }));
    }
  };

  const handleBookingConfirm = async (
    patientId: string,
    locationId: string,
    notes: string
  ) => {
    if (!selectedPractitioner || !selectedDate || !selectedSlot) {
      throw new Error('Missing booking data');
    }

    await createBooking(selectedPractitioner, {
      date: selectedDate,
      start: selectedSlot.start,
      end: selectedSlot.end,
      slot_duration: 30,
      patient_id: patientId,
      location_id: locationId,
      notes,
    });

    // Success: Close modal and refresh availability
    setTimeout(() => {
      setShowModal(false);
      setSelectedDate('');
      setSelectedSlot(null);
      loadAvailability(); // Refresh to show updated availability
    }, 1500);
  };

  const selectedPractitionerData = practitioners.find(p => p.id === selectedPractitioner);

  if (loadingData) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Cargando sistema de reservas...</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Reservar Cita</h1>
          <p className="page-description">
            Sistema nativo de reservas - Seleccione un horario disponible
          </p>
        </div>
      </div>

      <div className="page-content">
        {/* Diagnostic Panel (Development Only) */}
        {isDevelopment && (
          <div className="mb-6 p-4 bg-yellow-50 border-2 border-yellow-400 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-yellow-800">🔧 DIAGNOSTIC PANEL (Dev Only)</h3>
              <span className="text-xs text-yellow-600">NODE_ENV: {process.env.NODE_ENV}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div>
                <span className="font-semibold text-yellow-700">Practitioner ID:</span>
                <span className="ml-2 text-yellow-900">{diagnostic.practitionerId || 'null'}</span>
              </div>
              <div>
                <span className="font-semibold text-yellow-700">User Role:</span>
                <span className="ml-2 text-yellow-900">{diagnostic.role || 'null'}</span>
              </div>
              <div>
                <span className="font-semibold text-yellow-700">Date From:</span>
                <span className="ml-2 text-yellow-900">{diagnostic.dateFrom || 'null'}</span>
              </div>
              <div>
                <span className="font-semibold text-yellow-700">Date To:</span>
                <span className="ml-2 text-yellow-900">{diagnostic.dateTo || 'null'}</span>
              </div>
              <div className="col-span-2">
                <span className="font-semibold text-yellow-700">Last Request URL:</span>
                <div className="ml-2 text-yellow-900 break-all">{diagnostic.lastRequestUrl || 'N/A'}</div>
              </div>
              <div>
                <span className="font-semibold text-yellow-700">HTTP Status:</span>
                <span className={`ml-2 font-bold ${diagnostic.lastStatusCode === 200 ? 'text-green-600' : 'text-red-600'}`}>
                  {diagnostic.lastStatusCode || 'N/A'}
                </span>
              </div>
              <div>
                <span className="font-semibold text-yellow-700">Timestamp:</span>
                <span className="ml-2 text-yellow-900">
                  {diagnostic.timestamp ? new Date(diagnostic.timestamp).toLocaleTimeString() : 'N/A'}
                </span>
              </div>
              <div className="col-span-2">
                <span className="font-semibold text-yellow-700">Error Message:</span>
                <div className="ml-2 text-red-700 break-all">{diagnostic.lastErrorMessage || 'None'}</div>
              </div>
              <div className="col-span-2">
                <span className="font-semibold text-yellow-700">Response Body:</span>
                <pre className="ml-2 text-xs bg-yellow-100 p-2 rounded mt-1 overflow-auto max-h-32">
                  {diagnostic.lastResponseBody ? JSON.stringify(diagnostic.lastResponseBody, null, 2) : 'N/A'}
                </pre>
              </div>
              <div className="col-span-2">
                <span className="font-semibold text-yellow-700">Timezone:</span>
                <span className="ml-2 text-yellow-900">{diagnostic.timezone}</span>
              </div>
            </div>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center justify-between">
              <p className="text-sm text-red-800">{error}</p>
              <button
                onClick={() => {
                  setError('');
                  if (loadingData) {
                    loadInitialData();
                  } else {
                    loadAvailability();
                  }
                }}
                className="ml-4 px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors"
              >
                Reintentar
              </button>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Practitioner Selector */}
            {canSelectPractitioner ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Profesional
                </label>
                <select
                  value={selectedPractitioner}
                  onChange={(e) => setSelectedPractitioner(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {practitioners.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name} {p.specialty && `(${p.specialty})`}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Profesional
                </label>
                <div className="px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-gray-900">
                  {selectedPractitionerData?.display_name || 'Tu agenda'}
                </div>
              </div>
            )}

            {/* Date From */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Desde
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => handleDateFromChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Date To */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Hasta
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => handleDateToChange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Load Button (optional, since auto-load is enabled) */}
          <div className="mt-4">
            <button
              onClick={loadAvailability}
              disabled={loadingAvailability || !selectedPractitioner}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingAvailability ? 'Cargando...' : 'Actualizar disponibilidad'}
            </button>
          </div>
        </div>

        {/* Availability Calendar */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Horarios disponibles
          </h2>
          
          <AvailabilityCalendar
            availability={availability}
            onSlotSelect={handleSlotSelect}
            selectedDate={selectedDate}
            selectedSlot={selectedSlot || undefined}
            loading={loadingAvailability}
          />
        </div>

        {/* Booking Modal */}
        {selectedSlot && selectedPractitionerData && (
          <BookingModal
            isOpen={showModal}
            onClose={() => {
              setShowModal(false);
              setSelectedDate('');
              setSelectedSlot(null);
            }}
            date={selectedDate}
            slot={selectedSlot}
            practitionerName={selectedPractitionerData.display_name}
            patients={patients}
            locations={locations}
            onConfirm={handleBookingConfirm}
          />
        )}
      </div>
    </AppLayout>
  );
}

/**
 * Format Date object to YYYY-MM-DD
 */
function formatDateForInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
