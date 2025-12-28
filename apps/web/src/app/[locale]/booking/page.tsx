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

  // Initialize date range (today + 7 days)
  useEffect(() => {
    const today = new Date();
    const nextWeek = new Date(today);
    nextWeek.setDate(today.getDate() + 7);
    
    setDateFrom(formatDateForInput(today));
    setDateTo(formatDateForInput(nextWeek));
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

      // Auto-select practitioner
      if (practitionersData.length > 0) {
        // If practitioner role, try to find own practitioner
        if (isPractitioner && user) {
          const ownPractitioner = practitionersData.find(
            p => p.id === user.id // Assuming practitioner.user_id matches user.id
          );
          setSelectedPractitioner(ownPractitioner?.id || practitionersData[0].id);
        } else {
          setSelectedPractitioner(practitionersData[0].id);
        }
      }
    } catch (err: any) {
      console.error('Failed to load initial data:', err);
      setError('Error al cargar datos iniciales. Recargue la página.');
    } finally {
      setLoadingData(false);
    }
  };

  const loadAvailability = async () => {
    if (!selectedPractitioner || !dateFrom || !dateTo) return;

    try {
      setLoadingAvailability(true);
      setError('');

      const data = await fetchAvailability(
        selectedPractitioner,
        dateFrom,
        dateTo,
        30 // 30-minute slots
      );

      setAvailability(data.availability);
    } catch (err: any) {
      console.error('Failed to load availability:', err);
      if (err?.response?.status === 403) {
        setError('No tiene permisos para ver la disponibilidad de este profesional.');
      } else {
        setError('Error al cargar disponibilidad. Intente nuevamente.');
      }
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
        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-800">{error}</p>
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
                onChange={(e) => setDateFrom(e.target.value)}
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
                onChange={(e) => setDateTo(e.target.value)}
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
