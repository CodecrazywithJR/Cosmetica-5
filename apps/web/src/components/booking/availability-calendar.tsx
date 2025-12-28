/**
 * Availability Calendar Component
 * 
 * Sprint 4: UX Booking desde Availability
 * 
 * Displays available time slots for a practitioner across multiple days.
 * 
 * Features:
 * - Shows days with available slots
 * - Filters out slots that have already started (critical UX rule)
 * - Visual distinction: available, unavailable, selected
 * - Click to select a slot → triggers onSlotSelect callback
 * - Loading and error states
 * 
 * Critical rule: Does NOT show slots where slot_start <= now
 */

'use client';

import React, { useState, useEffect } from 'react';
import type { DayAvailability, TimeSlot } from '@/lib/types/booking';
import { filterPastSlots } from '@/lib/api/booking';

interface AvailabilityCalendarProps {
  availability: DayAvailability[];
  onSlotSelect: (date: string, slot: TimeSlot) => void;
  selectedDate?: string;
  selectedSlot?: TimeSlot;
  loading?: boolean;
}

export function AvailabilityCalendar({
  availability,
  onSlotSelect,
  selectedDate,
  selectedSlot,
  loading = false,
}: AvailabilityCalendarProps) {
  const [expandedDays, setExpandedDays] = useState<Set<string>>(new Set());

  // Auto-expand first day with slots on mount
  useEffect(() => {
    if (availability.length > 0) {
      const firstDayWithSlots = availability.find(day => day.available_slots > 0);
      if (firstDayWithSlots) {
        setExpandedDays(new Set([firstDayWithSlots.date]));
      }
    }
  }, [availability]);

  const toggleDay = (date: string) => {
    setExpandedDays(prev => {
      const next = new Set(prev);
      if (next.has(date)) {
        next.delete(date);
      } else {
        next.add(date);
      }
      return next;
    });
  };

  const isSlotSelected = (date: string, slot: TimeSlot) => {
    return selectedDate === date && 
           selectedSlot?.start === slot.start && 
           selectedSlot?.end === slot.end;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Cargando disponibilidad...</p>
        </div>
      </div>
    );
  }

  if (availability.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">No hay disponibilidad para el rango seleccionado.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {availability.map((day) => {
        // Filter out slots that already started (CRITICAL UX RULE)
        const futureSlots = filterPastSlots(day.date, day.slots);
        const hasAvailableSlots = futureSlots.length > 0;
        const isExpanded = expandedDays.has(day.date);

        return (
          <div
            key={day.date}
            className={`border rounded-lg overflow-hidden transition-all ${
              hasAvailableSlots ? 'border-gray-300' : 'border-gray-200 opacity-60'
            }`}
          >
            {/* Day Header */}
            <button
              onClick={() => hasAvailableSlots && toggleDay(day.date)}
              disabled={!hasAvailableSlots}
              className={`w-full px-4 py-3 flex items-center justify-between transition-colors ${
                hasAvailableSlots
                  ? 'hover:bg-gray-50 cursor-pointer'
                  : 'cursor-not-allowed bg-gray-50'
              }`}
            >
              <div className="flex items-center space-x-3">
                <div className="text-left">
                  <p className="font-medium text-gray-900">
                    {formatDate(day.date)}
                  </p>
                  <p className="text-sm text-gray-600">
                    {futureSlots.length} slot{futureSlots.length !== 1 ? 's' : ''} disponible{futureSlots.length !== 1 ? 's' : ''}
                  </p>
                </div>
              </div>
              {hasAvailableSlots && (
                <svg
                  className={`w-5 h-5 text-gray-400 transition-transform ${
                    isExpanded ? 'transform rotate-180' : ''
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              )}
            </button>

            {/* Slots Grid */}
            {isExpanded && hasAvailableSlots && (
              <div className="px-4 pb-4 pt-2">
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                  {futureSlots.map((slot) => {
                    const selected = isSlotSelected(day.date, slot);
                    return (
                      <button
                        key={`${slot.start}-${slot.end}`}
                        onClick={() => onSlotSelect(day.date, slot)}
                        className={`px-3 py-2 text-sm font-medium rounded-md transition-all ${
                          selected
                            ? 'bg-blue-600 text-white ring-2 ring-blue-400 ring-offset-2'
                            : 'bg-green-50 text-green-700 hover:bg-green-100 border border-green-200'
                        }`}
                      >
                        {slot.start}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Format date string to human-readable format
 * @param dateStr YYYY-MM-DD
 * @returns e.g., "Lunes, 5 de enero de 2026"
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  const options: Intl.DateTimeFormatOptions = {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  };
  
  // Use Spanish locale by default (can be made dynamic with i18n)
  return date.toLocaleDateString('es-ES', options);
}
