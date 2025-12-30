'use client';

import React, { useState, useEffect } from 'react';
import { format, startOfWeek, addDays, addWeeks, subWeeks } from 'date-fns';
import { es } from 'date-fns/locale';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';

import AppLayout from '@/components/layout/app-layout';
import { DataState } from '@/components/data-state';
import { routes, type Locale } from '@/lib/routing';

/* =======================
   Types
======================= */

type Encounter = {
  id: string;
  occurred_at: string;
  type: string;
  status: string;
  practitioner_name: string | null;
  treatment_count: number;
  attachments_summary: {
    photo_count: number;
    document_count: number;
  };
};

/* =======================
   API stub
======================= */

async function fetchEncounters(): Promise<{ results: Encounter[] }> {
  return { results: [] };
}

/* =======================
   Page
======================= */

export default function EncountersPage() {
  const t = useTranslations('encounters.list.patient');
  const locale = useLocale() as Locale;
  const router = useRouter();

  /* -----------------------
     State
  ----------------------- */

  const [currentWeekStart, setCurrentWeekStart] = useState<Date>(
    startOfWeek(new Date(), { weekStartsOn: 1 })
  );
  const [selectedDay, setSelectedDay] = useState(
    format(new Date(), 'yyyy-MM-dd')
  );
  const [practitioner, setPractitioner] = useState('');
  const [status, setStatus] = useState('');

  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  /* -----------------------
     Effects
  ----------------------- */

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      setForbidden(false);

      try {
        const data = await fetchEncounters();
        setEncounters(data.results);
      } catch {
        setError('error');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [selectedDay, practitioner, status]);

  /* -----------------------
     Render states
  ----------------------- */

  if (loading) {
    return (
      <AppLayout>
        <DataState isLoading loadingMessage={t('title')} />
      </AppLayout>
    );
  }

  if (forbidden) {
    return (
      <AppLayout>
        <DataState errorTitle="Forbidden" />
      </AppLayout>
    );
  }

  if (error) {
    return (
      <AppLayout>
        <DataState errorTitle="Error" />
      </AppLayout>
    );
  }

  /* -----------------------
     Main render
  ----------------------- */

  return (
    <AppLayout>
      <div className="page-header">
        <h1 className="page-title">{t('title')}</h1>
      </div>

      <div className="page-content">
        {/* Calendar */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <button onClick={() => setCurrentWeekStart(subWeeks(currentWeekStart, 1))}>
              ← Anterior
            </button>
            <button onClick={() => setCurrentWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 }))}>
              Hoy
            </button>
            <button onClick={() => setCurrentWeekStart(addWeeks(currentWeekStart, 1))}>
              Siguiente →
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 12 }}>
            {[0, 1, 2, 3, 4, 5, 6].map((offset) => {
              const date = addDays(currentWeekStart, offset);
              const key = format(date, 'yyyy-MM-dd');

              return (
                <div
                  key={key}
                  onClick={() => setSelectedDay(key)}
                  style={{
                    border: selectedDay === key ? '2px solid #4f46e5' : '1px solid #ddd',
                    padding: 12,
                    cursor: 'pointer',
                  }}
                >
                  <div>{format(date, 'EEEE', { locale: es })}</div>
                  <div>{format(date, 'd')}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Table */}
        <div className="bg-white border rounded">
          {encounters.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              {t('empty.message')}
            </div>
          ) : (
            <table className="min-w-full">
              <tbody>
                {encounters.map((e) => (
                  <tr
                    key={e.id}
                    onClick={() =>
                      router.push(routes.encounters.detail(locale, e.id))
                    }
                    style={{ cursor: 'pointer' }}
                  >
                    <td>{e.occurred_at}</td>
                    <td>{e.type}</td>
                    <td>{e.status}</td>
                    <td>{e.practitioner_name ?? '—'}</td>
                    <td>{e.treatment_count}</td>
                    <td>
                      {e.attachments_summary.photo_count > 0 && `📷 ${e.attachments_summary.photo_count}`}
                      {e.attachments_summary.document_count > 0 && ` 📄 ${e.attachments_summary.document_count}`}
                      {e.attachments_summary.photo_count === 0 &&
                        e.attachments_summary.document_count === 0 &&
                        '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
