/**
 * Edit Legal Entity Page
 * Full-page form to update an existing Legal Entity.
 * Auth guard delegated to AppLayout. Role guard inside AppLayout children.
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import { DataState } from '@/components/data-state';
import { useAuth, ROLES } from '@/lib/auth-context';
import { routes, type Locale } from '@/lib/routing';
import {
  useLegalEntity,
  useUpdateLegalEntity,
  type LegalEntityDetail,
  type LegalEntityUpdateData,
} from '@/lib/hooks/use-legal-entities';

export default function EditLegalEntityPage() {
  const params = useParams<{ id: string }>();

  return (
    <AppLayout>
      <EditLegalEntityContent id={params.id} />
    </AppLayout>
  );
}

/* ------------------------------------------------------------------ */
/*  Content wrapper (handles loading / error)                          */
/* ------------------------------------------------------------------ */

function EditLegalEntityContent({ id }: { id: string }) {
  const t = useTranslations('admin.legalEntities');
  const { data: entity, isLoading, error } = useLegalEntity(id);

  return (
    <DataState
      isLoading={isLoading}
      error={error as Error | null}
      errorTitle={t('messages.errorLoad')}
    >
      {entity && <EditLegalEntityForm entity={entity} />}
    </DataState>
  );
}

/* ------------------------------------------------------------------ */
/*  Form                                                               */
/* ------------------------------------------------------------------ */

function EditLegalEntityForm({ entity }: { entity: LegalEntityDetail }) {
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('admin.legalEntities');
  const updateMutation = useUpdateLegalEntity();

  const [form, setForm] = useState<LegalEntityUpdateData>({
    legal_name: entity.legal_name,
    trade_name: entity.trade_name ?? '',
    country_code: entity.country_code,
    siren: entity.siren ?? '',
    siret: entity.siret ?? '',
    vat_number: entity.vat_number ?? '',
    address_line_1: entity.address_line_1 ?? '',
    address_line_2: entity.address_line_2 ?? '',
    postal_code: entity.postal_code ?? '',
    city: entity.city ?? '',
    legal_email: entity.legal_email,
    phone: entity.phone ?? '',
    currency: entity.currency ?? 'EUR',
    timezone: entity.timezone ?? 'Europe/Paris',
    is_active: entity.is_active,
  });

  const [saved, setSaved] = useState(false);

  // Reset saved flag after 3s
  useEffect(() => {
    if (!saved) return;
    const timer = setTimeout(() => setSaved(false), 3000);
    return () => clearTimeout(timer);
  }, [saved]);

  const set = (field: keyof LegalEntityUpdateData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate(
      { id: entity.id, data: form },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28 }}>
        <button
          className="btn-secondary btn-sm"
          type="button"
          onClick={() => router.push(routes.legalEntities.list(locale))}
        >
          ←
        </button>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#111827', margin: 0 }}>
          {t('editTitle')}
        </h1>
        <span style={{ fontSize: 14, color: '#9ca3af', marginLeft: 4 }}>
          #{entity.id.slice(0, 8)}
        </span>
      </div>

      {updateMutation.isError && (
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 8,
            padding: '12px 16px',
            marginBottom: 20,
            color: '#991b1b',
            fontSize: 14,
          }}
        >
          {t('messages.errorUpdate')}
        </div>
      )}

      {saved && (
        <div
          style={{
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            borderRadius: 8,
            padding: '12px 16px',
            marginBottom: 20,
            color: '#065f46',
            fontSize: 14,
          }}
        >
          {t('messages.updated')}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Section: Identity */}
        <SectionCard title={t('form.sectionIdentity')}>
          <FormGrid>
            <Field label={t('form.legalName')} required>
              <input className="form-input" value={form.legal_name ?? ''} onChange={set('legal_name')} required />
            </Field>
            <Field label={t('form.tradeName')}>
              <input className="form-input" value={form.trade_name ?? ''} onChange={set('trade_name')} />
            </Field>
            <Field label={t('form.countryCode')} required>
              <input className="form-input" value={form.country_code ?? ''} onChange={set('country_code')} maxLength={2} required style={{ textTransform: 'uppercase' }} />
            </Field>
            <Field label={t('form.siren')}>
              <input className="form-input" value={form.siren ?? ''} onChange={set('siren')} maxLength={9} />
            </Field>
            <Field label={t('form.siret')}>
              <input className="form-input" value={form.siret ?? ''} onChange={set('siret')} maxLength={14} />
            </Field>
            <Field label={t('form.vatNumber')}>
              <input className="form-input" value={form.vat_number ?? ''} onChange={set('vat_number')} maxLength={20} />
            </Field>
          </FormGrid>
        </SectionCard>

        {/* Section: Address */}
        <SectionCard title={t('form.sectionAddress')}>
          <FormGrid>
            <Field label={t('form.addressLine1')} wide>
              <input className="form-input" value={form.address_line_1 ?? ''} onChange={set('address_line_1')} />
            </Field>
            <Field label={t('form.addressLine2')} wide>
              <input className="form-input" value={form.address_line_2 ?? ''} onChange={set('address_line_2')} />
            </Field>
            <Field label={t('form.postalCode')}>
              <input className="form-input" value={form.postal_code ?? ''} onChange={set('postal_code')} maxLength={10} />
            </Field>
            <Field label={t('form.city')}>
              <input className="form-input" value={form.city ?? ''} onChange={set('city')} />
            </Field>
          </FormGrid>
        </SectionCard>

        {/* Section: Contact */}
        <SectionCard title={t('form.sectionContact')}>
          <FormGrid>
            <Field label={t('form.legalEmail')} required>
              <input className="form-input" type="email" value={form.legal_email ?? ''} onChange={set('legal_email')} required />
            </Field>
            <Field label={t('form.phone')}>
              <input className="form-input" type="tel" value={form.phone ?? ''} onChange={set('phone')} maxLength={30} />
            </Field>
            <Field label={t('form.currency')}>
              <input className="form-input" value={form.currency ?? ''} onChange={set('currency')} maxLength={3} style={{ textTransform: 'uppercase' }} />
            </Field>
            <Field label={t('form.timezone')}>
              <input className="form-input" value={form.timezone ?? ''} onChange={set('timezone')} />
            </Field>
          </FormGrid>
        </SectionCard>

        {/* Section: Status */}
        <SectionCard title={t('form.sectionStatus')}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={form.is_active ?? true}
              onChange={set('is_active')}
              style={{ width: 18, height: 18, accentColor: 'var(--primary-500)' }}
            />
            <span style={{ fontSize: 14, fontWeight: 500, color: '#374151' }}>
              {t('form.isActive')}
            </span>
          </label>
        </SectionCard>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 8, marginBottom: 40 }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => router.push(routes.legalEntities.list(locale))}
            style={{ padding: '10px 20px', borderRadius: 8, fontSize: 14 }}
          >
            {t('actions.cancel')}
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={updateMutation.isPending}
            style={{ padding: '10px 20px', borderRadius: 8, fontSize: 14, fontWeight: 600 }}
          >
            {updateMutation.isPending ? '…' : t('actions.save')}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ================================================================== */
/*  Helpers (same as create page)                                      */
/* ================================================================== */

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ marginBottom: 20, padding: '20px 24px' }}>
      <h2 style={{ fontSize: 15, fontWeight: 700, color: '#374151', marginBottom: 16, marginTop: 0 }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

function FormGrid({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px 20px' }}>
      {children}
    </div>
  );
}

function Field({
  label,
  required,
  wide,
  children,
}: {
  label: string;
  required?: boolean;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div style={wide ? { gridColumn: '1 / -1' } : undefined}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 4 }}>
        {label}
        {required && <span style={{ color: '#ef4444', marginLeft: 3 }}>*</span>}
      </label>
      {children}
    </div>
  );
}
