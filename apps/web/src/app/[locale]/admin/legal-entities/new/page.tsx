/**
 * Create Legal Entity Page
 * Full-page form to create a new Legal Entity + admin user.
 * Auth guard delegated to AppLayout. Role guard inside AppLayout children.
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import AppLayout from '@/components/layout/app-layout';
import { useAuth, ROLES } from '@/lib/auth-context';
import { routes, type Locale } from '@/lib/routing';
import { useCreateLegalEntity, type LegalEntityCreateData } from '@/lib/hooks/use-legal-entities';

export default function CreateLegalEntityPage() {
  return (
    <AppLayout>
      <CreateLegalEntityForm />
    </AppLayout>
  );
}

/* ------------------------------------------------------------------ */
/*  Form                                                               */
/* ------------------------------------------------------------------ */

function CreateLegalEntityForm() {
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('admin.legalEntities');
  const createMutation = useCreateLegalEntity();

  const [form, setForm] = useState<LegalEntityCreateData>({
    legal_name: '',
    country_code: '',
    legal_email: '',
    admin_email: '',
    trade_name: '',
    siren: '',
    siret: '',
    vat_number: '',
    address_line_1: '',
    address_line_2: '',
    postal_code: '',
    city: '',
    phone: '',
    currency: 'EUR',
    timezone: 'Europe/Paris',
    admin_first_name: '',
    admin_last_name: '',
  });

  const [tempPassword, setTempPassword] = useState<string | null>(null);

  const set = (field: keyof LegalEntityCreateData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(form, {
      onSuccess: (data: any) => {
        if (data?.temporary_password) {
          setTempPassword(data.temporary_password);
        } else {
          router.push(routes.legalEntities.list(locale));
        }
      },
    });
  };

  /* ----- Temp-password confirmation screen ----- */
  if (tempPassword) {
    return (
      <div style={{ maxWidth: 520, margin: '40px auto', textAlign: 'center' }}>
        <div className="card" style={{ padding: 32 }}>
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ margin: '0 auto 16px' }}>
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: '#111827', marginBottom: 8 }}>
            {t('messages.created')}
          </h2>
          <p style={{ fontSize: 14, color: '#6b7280', marginBottom: 20 }}>
            {t('messages.tempPasswordNotice')}
          </p>
          <div
            style={{
              background: '#fef3c7',
              border: '1px solid #fbbf24',
              borderRadius: 8,
              padding: '14px 20px',
              fontFamily: 'monospace',
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: '0.08em',
              color: '#92400e',
              marginBottom: 24,
              userSelect: 'all',
            }}
          >
            {tempPassword}
          </div>
          <button
            className="btn-primary"
            onClick={() => router.push(routes.legalEntities.list(locale))}
            style={{ padding: '10px 24px', borderRadius: 8, fontSize: 14 }}
          >
            {t('messages.goToList')}
          </button>
        </div>
      </div>
    );
  }

  /* ----- Form ----- */
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
          {t('createTitle')}
        </h1>
      </div>

      {createMutation.isError && (
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
          {t('messages.errorCreate')}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Section: Identity */}
        <SectionCard title={t('form.sectionIdentity')}>
          <FormGrid>
            <Field label={t('form.legalName')} required>
              <input className="form-input" value={form.legal_name} onChange={set('legal_name')} required />
            </Field>
            <Field label={t('form.tradeName')}>
              <input className="form-input" value={form.trade_name} onChange={set('trade_name')} />
            </Field>
            <Field label={t('form.countryCode')} required>
              <input className="form-input" value={form.country_code} onChange={set('country_code')} maxLength={2} required style={{ textTransform: 'uppercase' }} />
            </Field>
            <Field label={t('form.siren')}>
              <input className="form-input" value={form.siren} onChange={set('siren')} maxLength={9} />
            </Field>
            <Field label={t('form.siret')}>
              <input className="form-input" value={form.siret} onChange={set('siret')} maxLength={14} />
            </Field>
            <Field label={t('form.vatNumber')}>
              <input className="form-input" value={form.vat_number} onChange={set('vat_number')} maxLength={20} />
            </Field>
          </FormGrid>
        </SectionCard>

        {/* Section: Address */}
        <SectionCard title={t('form.sectionAddress')}>
          <FormGrid>
            <Field label={t('form.addressLine1')} wide>
              <input className="form-input" value={form.address_line_1} onChange={set('address_line_1')} />
            </Field>
            <Field label={t('form.addressLine2')} wide>
              <input className="form-input" value={form.address_line_2} onChange={set('address_line_2')} />
            </Field>
            <Field label={t('form.postalCode')}>
              <input className="form-input" value={form.postal_code} onChange={set('postal_code')} maxLength={10} />
            </Field>
            <Field label={t('form.city')}>
              <input className="form-input" value={form.city} onChange={set('city')} />
            </Field>
          </FormGrid>
        </SectionCard>

        {/* Section: Contact */}
        <SectionCard title={t('form.sectionContact')}>
          <FormGrid>
            <Field label={t('form.legalEmail')} required>
              <input className="form-input" type="email" value={form.legal_email} onChange={set('legal_email')} required />
            </Field>
            <Field label={t('form.phone')}>
              <input className="form-input" type="tel" value={form.phone} onChange={set('phone')} maxLength={30} />
            </Field>
            <Field label={t('form.currency')}>
              <input className="form-input" value={form.currency} onChange={set('currency')} maxLength={3} style={{ textTransform: 'uppercase' }} />
            </Field>
            <Field label={t('form.timezone')}>
              <input className="form-input" value={form.timezone} onChange={set('timezone')} />
            </Field>
          </FormGrid>
        </SectionCard>

        {/* Section: Admin User */}
        <SectionCard title={t('form.sectionAdmin')}>
          <FormGrid>
            <Field label={t('form.adminEmail')} required>
              <input className="form-input" type="email" value={form.admin_email} onChange={set('admin_email')} required />
            </Field>
            <Field label={t('form.adminFirstName')}>
              <input className="form-input" value={form.admin_first_name} onChange={set('admin_first_name')} />
            </Field>
            <Field label={t('form.adminLastName')}>
              <input className="form-input" value={form.admin_last_name} onChange={set('admin_last_name')} />
            </Field>
          </FormGrid>
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
            disabled={createMutation.isPending}
            style={{ padding: '10px 20px', borderRadius: 8, fontSize: 14, fontWeight: 600 }}
          >
            {createMutation.isPending ? '…' : t('actions.create')}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ================================================================== */
/*  Helpers                                                            */
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
