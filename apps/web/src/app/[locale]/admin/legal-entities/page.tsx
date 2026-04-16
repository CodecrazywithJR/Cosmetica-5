/**
 * Legal Entities List Page
 * Admin panel — list all legal entities with CRUD actions.
 * Protected: superuser OR ADMIN role.
 * Fully internationalized with next-intl (namespace: admin.legalEntities).
 *
 * Auth guard is delegated to AppLayout (checks isInitializing + authError).
 * Role guard is INSIDE AppLayout so it never fires during init.
 */

'use client';

import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import { DataState } from '@/components/data-state';
import { useAuth, ROLES } from '@/lib/auth-context';
import { routes, type Locale } from '@/lib/routing';
import { useLegalEntities, type LegalEntity } from '@/lib/hooks/use-legal-entities';

export default function LegalEntitiesListPage() {
  return (
    <AppLayout>
      <LegalEntitiesContent />
    </AppLayout>
  );
}

function LegalEntitiesContent() {
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('admin.legalEntities');
  const { data: entities, isLoading, error } = useLegalEntities();

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#111827' }}>
          {t('pageTitle')}
        </h1>
        <button
          className="btn-primary"
          onClick={() => router.push(routes.legalEntities.create(locale))}
          style={{ padding: '10px 20px', borderRadius: 8, fontSize: 14, fontWeight: 600 }}
        >
          {t('create')}
        </button>
      </div>

      <DataState
        isLoading={isLoading}
        error={error as Error | null}
        errorTitle={t('messages.errorLoad')}
        isEmpty={!entities || entities.length === 0}
        emptyMessage={t('empty')}
        emptyDescription={t('emptyHint')}
        emptyAction={{
          label: t('create'),
          onClick: () => router.push(routes.legalEntities.create(locale)),
        }}
      >
        {entities && entities.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0 }}>
              <thead>
                <tr>
                  {['tradeName', 'legalName', 'country', 'siret', 'active', 'users'].map((col) => (
                    <th
                      key={col}
                      style={{
                        textAlign: 'left',
                        padding: '10px 14px',
                        fontSize: 12,
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                        color: '#9ca3af',
                        borderBottom: '1px solid #e5e7eb',
                      }}
                    >
                      {t(`columns.${col}` as any)}
                    </th>
                  ))}
                  <th
                    style={{
                      textAlign: 'right',
                      padding: '10px 14px',
                      fontSize: 12,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      color: '#9ca3af',
                      borderBottom: '1px solid #e5e7eb',
                    }}
                  >
                    {t('columns.actions')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {entities.map((entity) => (
                  <EntityRow key={entity.id} entity={entity} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataState>
    </div>
  );
}

function EntityRow({ entity }: { entity: LegalEntity }) {
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('admin.legalEntities');

  return (
    <tr
      style={{ cursor: 'pointer' }}
      onClick={() => router.push(routes.legalEntities.edit(locale, entity.id))}
    >
      <td style={{ padding: '14px', borderBottom: '1px solid #f3f4f6', fontSize: 14, fontWeight: 500, color: '#111827' }}>
        {entity.trade_name || '—'}
      </td>
      <td style={{ padding: '14px', borderBottom: '1px solid #f3f4f6', fontSize: 14, color: '#4b5563' }}>
        {entity.legal_name}
      </td>
      <td style={{ padding: '14px', borderBottom: '1px solid #f3f4f6', fontSize: 14, color: '#4b5563' }}>
        {entity.country_code}
      </td>
      <td style={{ padding: '14px', borderBottom: '1px solid #f3f4f6', fontSize: 14, color: '#4b5563', fontFamily: 'monospace' }}>
        {entity.siret || '—'}
      </td>
      <td style={{ padding: '14px', borderBottom: '1px solid #f3f4f6' }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '3px 10px',
            borderRadius: 9999,
            fontSize: 12,
            fontWeight: 600,
            backgroundColor: entity.is_active ? '#d1fae5' : '#fee2e2',
            color: entity.is_active ? '#065f46' : '#991b1b',
          }}
        >
          {entity.is_active ? t('status.active') : t('status.inactive')}
        </span>
      </td>
      <td style={{ padding: '14px', borderBottom: '1px solid #f3f4f6', fontSize: 14, color: '#6b7280' }}>
        {entity.user_count}
      </td>
      <td style={{ padding: '14px', borderBottom: '1px solid #f3f4f6', textAlign: 'right' }}>
        <button
          className="btn-secondary"
          onClick={(e) => {
            e.stopPropagation();
            router.push(routes.legalEntities.edit(locale, entity.id));
          }}
          style={{ padding: '6px 14px', borderRadius: 6, fontSize: 13 }}
        >
          {t('edit')}
        </button>
      </td>
    </tr>
  );
}
