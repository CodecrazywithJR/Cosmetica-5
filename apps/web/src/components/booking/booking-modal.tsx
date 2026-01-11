/**
 * Booking Modal Component
 * 
 * Sprint 4: UX Booking desde Availability
 * 
 * Confirmation modal for creating an appointment.
 * 
 * Features:
 * - Shows selected date, time, practitioner
 * - Patient and location selectors
 * - Loading state during API call (disables button to prevent double-submit)
 * - Success state with appointment details
 * - Error state with human-readable messages
 * - Handles backend validation errors (slot already started, not available, etc.)
 * 
 * States:
 * - idle: Ready to book
 * - loading: Creating appointment
 * - success: Appointment created
 * - error: Booking failed
 */

'use client';

import React, { useState, useEffect } from 'react';
import type { TimeSlot, PatientInfo, LocationInfo, BookingError } from '@/lib/types/booking';

type BookingState = 'idle' | 'loading' | 'success' | 'error';

interface BookingModalProps {
  isOpen: boolean;
  onClose: () => void;
  date: string;
  slot: TimeSlot;
  practitionerName: string;
  patients: PatientInfo[];
  locations: LocationInfo[];
  onConfirm: (patientId: string, locationId: string, notes: string) => Promise<void>;
}

export function BookingModal({
  isOpen,
  onClose,
  date,
  slot,
  practitionerName,
  patients,
  locations,
  onConfirm,
}: BookingModalProps) {
  const [state, setState] = useState<BookingState>('idle');
  const [selectedPatient, setSelectedPatient] = useState<string>('');
  const [selectedLocation, setSelectedLocation] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [appointmentId, setAppointmentId] = useState<string>('');

  // Auto-select first patient and location
  useEffect(() => {
    if (isOpen && patients.length > 0 && !selectedPatient) {
      setSelectedPatient(patients[0].id);
    }
    if (isOpen && locations.length > 0 && !selectedLocation) {
      setSelectedLocation(locations[0].id);
    }
  }, [isOpen, patients, locations, selectedPatient, selectedLocation]);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setState('idle');
      setNotes('');
      setError('');
      setAppointmentId('');
    }
  }, [isOpen]);

  const handleConfirm = async () => {
    if (!selectedPatient || !selectedLocation) {
      setError('Seleccione paciente y ubicación');
      return;
    }

    setState('loading');
    setError('');

    try {
      await onConfirm(selectedPatient, selectedLocation, notes);
      setState('success');
      // Modal will auto-close after success (handled by parent)
    } catch (err: any) {
      setState('error');
      
      // Parse backend error
      const errorData = err?.response?.data as BookingError;
      
      if (errorData?.error === 'Slot already started') {
        setError('⏱️ Este horario ya ha comenzado. Por favor, seleccione un horario futuro.');
      } else if (errorData?.error === 'Slot not available') {
        setError('❌ Este horario ya no está disponible. Otro usuario lo reservó recientemente.');
      } else if (err?.response?.status === 403) {
        setError('🔒 No tiene permisos para crear citas.');
      } else if (err?.response?.status === 400) {
        setError(`⚠️ Error de validación: ${errorData?.details || 'Datos inválidos'}`);
      } else {
        setError('❌ Error al crear la cita. Intente nuevamente.');
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={state === 'idle' || state === 'error' ? onClose : undefined}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
          {/* Close button (only when not loading) */}
          {state !== 'loading' && (
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}

          {/* Success State */}
          {state === 'success' && (
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100 mb-4">
                <svg className="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                ¡Cita confirmada!
              </h3>
              <p className="text-sm text-gray-600 mb-6">
                La cita se ha creado exitosamente en el sistema.
              </p>
              <button
                onClick={onClose}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Cerrar
              </button>
            </div>
          )}

          {/* Idle / Loading / Error States */}
          {state !== 'success' && (
            <>
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Confirmar reserva
              </h3>

              {/* Appointment Details */}
              <div className="bg-gray-50 rounded-lg p-4 mb-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Fecha:</span>
                  <span className="font-medium text-gray-900">{formatDate(date)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Horario:</span>
                  <span className="font-medium text-gray-900">{slot.start} - {slot.end}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Profesional:</span>
                  <span className="font-medium text-gray-900">{practitionerName}</span>
                </div>
              </div>

              {/* Patient Selector */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Paciente *
                </label>
                <select
                  value={selectedPatient}
                  onChange={(e) => setSelectedPatient(e.target.value)}
                  disabled={state === 'loading'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  required
                >
                  {patients.map((patient) => (
                    <option key={patient.id} value={patient.id}>
                      {patient.first_name} {patient.last_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Location Selector */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Ubicación *
                </label>
                <select
                  value={selectedLocation}
                  onChange={(e) => setSelectedLocation(e.target.value)}
                  disabled={state === 'loading'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  required
                >
                  {locations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Notes */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notas (opcional)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  disabled={state === 'loading'}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  placeholder="Información adicional sobre la cita..."
                />
              </div>

              {/* Error Message */}
              {state === 'error' && error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex space-x-3">
                <button
                  onClick={onClose}
                  disabled={state === 'loading'}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={state === 'loading' || !selectedPatient || !selectedLocation}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {state === 'loading' ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Reservando...
                    </>
                  ) : (
                    'Confirmar reserva'
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Format date string to human-readable format
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  const options: Intl.DateTimeFormatOptions = {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  };
  return date.toLocaleDateString('es-ES', options);
}
