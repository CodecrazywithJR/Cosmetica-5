/**
 * Encounter Detail Page
 * View/edit encounter with treatments (Practitioner workflow)
 * Fully internationalized with next-intl
 */

'use client';

import AppLayout from '@/components/layout/app-layout';
import { RBACGuard } from '@/components/rbac-guard';
import { ROLES } from '@/lib/auth-context';
import { useEncounter, useAddTreatment, useFinalizeEncounter } from '@/lib/hooks/use-encounters';
import { useGenerateProposal } from '@/lib/hooks/use-proposals';
import { useParams, useRouter } from 'next/navigation';
import { useState, useMemo } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { routes, type Locale } from '@/lib/routing';

export default function EncounterDetailPage() {
  const t = useTranslations('clinical');
  const tCommon = useTranslations('common');
  const locale = useLocale() as Locale;
  const params = useParams();
  const router = useRouter();
  const encounterId = params.id as string;

  const { data: encounter, isLoading, error } = useEncounter(encounterId);
  const addTreatment = useAddTreatment();
  const finalize = useFinalizeEncounter();
  const generateProposal = useGenerateProposal();

  const [showAddTreatmentModal, setShowAddTreatmentModal] = useState(false);
  const [showFinalizeModal, setShowFinalizeModal] = useState(false);
  const [treatmentId, setTreatmentId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [unitPrice, setUnitPrice] = useState('');
  const [notes, setNotes] = useState('');

  // Date/time formatter using current language
  const dateTimeFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }),
    [locale]
  );

  // Currency formatter using current language
  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'USD',
      }),
    [locale]
  );

  const handleAddTreatment = async () => {
    if (!treatmentId || quantity <= 0) return;

    try {
      await addTreatment.mutateAsync({
        encounterId,
        treatmentId,
        quantity,
        unitPrice: unitPrice ? parseFloat(unitPrice) : undefined,
        notes: notes || undefined,
      });
      setShowAddTreatmentModal(false);
      setTreatmentId('');
      setQuantity(1);
      setUnitPrice('');
      setNotes('');
    } catch (err) {
      console.error('Error adding treatment:', err);
    }
  };

  const handleFinalize = async () => {
    try {
      await finalize.mutateAsync(encounterId);
      setShowFinalizeModal(false);
    } catch (err) {
      console.error('Error finalizing encounter:', err);
    }
  };

  const handleGenerateProposal = async () => {
    try {
      const result = await generateProposal.mutateAsync({ encounterId });
      alert(`${t('clinical:messages.proposalGenerated')} ${result.proposal_id}`);
      router.push(routes.proposals.list(locale));
    } catch (err) {
      console.error('Error generating proposal:', err);
    }
  };

  // Format encounter type for display
  const getEncounterTypeKey = (type: string): string => {
    return type.replace(/-/g, '_');
  };

  if (isLoading) {
    return (
      <AppLayout>
        <div className="card">
          <div className="card-body">{t('clinical:loading.encounter')}</div>
        </div>
      </AppLayout>
    );
  }

  if (error || !encounter) {
    return (
      <AppLayout>
        <div className="alert-error">
          {t('clinical:errors.loadingFailed')}: {(error as any)?.message || t('clinical:errors.notFound')}
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <RBACGuard roles={[ROLES.ADMIN, ROLES.PRACTITIONER, ROLES.CLINICAL_OPS]}>
        <div>
          <div className="page-header">
            <h1>{t('clinical:encounter.title')}</h1>
            <span className={`badge badge-${encounter.status}`}>
              {t(`clinical:encounter.status.${encounter.status}`, encounter.status)}
            </span>
          </div>

          {/* Patient Info Card */}
          <div className="card mb-4">
            <div className="card-header">
              <h2>{t('clinical:sections.patientInfo')}</h2>
            </div>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:patientLabels.name')}
                  </div>
                  <div style={{ fontWeight: 500 }}>{encounter.patient.full_name}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:patientLabels.email')}
                  </div>
                  <div>{encounter.patient.email}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:patientLabels.phone')}
                  </div>
                  <div>{encounter.patient.phone || '—'}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:patientLabels.dateOfBirth')}
                  </div>
                  <div>{encounter.patient.birth_date || '—'}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Encounter Info Card */}
          <div className="card mb-4">
            <div className="card-header">
              <h2>{t('clinical:sections.encounterInfo')}</h2>
            </div>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:encounterLabels.practitioner')}
                  </div>
                  <div style={{ fontWeight: 500 }}>{encounter.practitioner?.display_name || '—'}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:encounterLabels.type')}
                  </div>
                  <div>
                    {t(`clinical:encounter.type.${getEncounterTypeKey(encounter.type)}`, encounter.type)}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:encounterLabels.date')}
                  </div>
                  <div>{dateTimeFormatter.format(new Date(encounter.occurred_at))}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:encounterLabels.status')}
                  </div>
                  <div>
                    <span className={`badge badge-${encounter.status}`}>
                      {t(`clinical:encounter.status.${encounter.status}`, encounter.status)}
                    </span>
                  </div>
                </div>
              </div>

              {encounter.chief_complaint && (
                <div style={{ marginTop: '16px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:encounterLabels.chiefComplaint')}
                  </div>
                  <div>{encounter.chief_complaint}</div>
                </div>
              )}

              {encounter.assessment && (
                <div style={{ marginTop: '16px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:encounterLabels.assessment')}
                  </div>
                  <div>{encounter.assessment}</div>
                </div>
              )}

              {encounter.plan && (
                <div style={{ marginTop: '16px' }}>
                  <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                    {t('clinical:encounterLabels.plan')}
                  </div>
                  <div>{encounter.plan}</div>
                </div>
              )}
            </div>
          </div>

          {/* Treatments Card */}
          <div className="card mb-4">
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2>{t('clinical:sections.treatments')}</h2>
              {encounter.status === 'draft' && (
                <button
                  onClick={() => setShowAddTreatmentModal(true)}
                  className="btn-primary btn-sm"
                >
                  {t('clinical:actions.addTreatment')}
                </button>
              )}
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              {encounter.encounter_treatments && encounter.encounter_treatments.length > 0 ? (
                <table className="table">
                  <thead>
                    <tr>
                      <th>{t('clinical:treatmentLabels.treatment')}</th>
                      <th>{t('clinical:treatmentLabels.quantity')}</th>
                      <th>{t('clinical:treatmentLabels.unitPrice')}</th>
                      <th>{t('clinical:treatmentLabels.total')}</th>
                      <th>{t('clinical:treatmentLabels.notes')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {encounter.encounter_treatments.map((et) => (
                      <tr key={et.id}>
                        <td style={{ fontWeight: 500 }}>{et.treatment.name}</td>
                        <td>{et.quantity}</td>
                        <td>{currencyFormatter.format(Number(et.unit_price || et.effective_price))}</td>
                        <td style={{ fontWeight: 500 }}>{currencyFormatter.format(Number(et.total_price))}</td>
                        <td>{et.notes || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--gray-600)' }}>
                  {t('clinical:empty.noTreatments')}
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            {encounter.status === 'draft' && (
              <button
                onClick={() => setShowFinalizeModal(true)}
                className="btn-primary"
                disabled={finalize.isPending || !encounter.encounter_treatments?.length}
                title={!encounter.encounter_treatments?.length ? t('clinical:messages.mustAddTreatments') : ''}
              >
                {finalize.isPending ? t('clinical:actions.finalizing') : t('clinical:actions.finalize')}
              </button>
            )}

            {encounter.status === 'finalized' && (
              <button
                onClick={handleGenerateProposal}
                className="btn-primary"
                disabled={generateProposal.isPending}
              >
                {generateProposal.isPending ? t('clinical:actions.generating') : t('clinical:actions.generateProposal')}
              </button>
            )}

            <button onClick={() => router.back()} className="btn-secondary">
              {t('clinical:actions.back')}
            </button>
          </div>

          {/* Add Treatment Modal */}
          {showAddTreatmentModal && (
            <div
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0,0,0,0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
              }}
              onClick={() => setShowAddTreatmentModal(false)}
            >
              <div
                className="card"
                style={{ width: '500px', maxWidth: '90%' }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="card-header">
                  <h2>{t('clinical:modals.addTreatmentTitle')}</h2>
                </div>
                <div className="card-body">
                  <div className="form-group">
                    <label htmlFor="treatmentId">{t('clinical:modals.treatmentIdLabel')}</label>
                    <input
                      id="treatmentId"
                      type="text"
                      value={treatmentId}
                      onChange={(e) => setTreatmentId(e.target.value)}
                      placeholder={t('clinical:modals.treatmentIdPlaceholder')}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="quantity">{t('clinical:modals.quantityLabel')}</label>
                    <input
                      id="quantity"
                      type="number"
                      min="1"
                      value={quantity}
                      onChange={(e) => setQuantity(parseInt(e.target.value))}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="unitPrice">{t('clinical:modals.unitPriceLabel')}</label>
                    <input
                      id="unitPrice"
                      type="number"
                      step="0.01"
                      value={unitPrice}
                      onChange={(e) => setUnitPrice(e.target.value)}
                      placeholder={t('clinical:modals.unitPricePlaceholder')}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="notes">{t('clinical:modals.notesLabel')}</label>
                    <textarea
                      id="notes"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                      placeholder={t('clinical:modals.notesPlaceholder')}
                    />
                  </div>

                  <div className="flex gap-2 justify-between">
                    <button
                      onClick={() => setShowAddTreatmentModal(false)}
                      className="btn-secondary"
                      disabled={addTreatment.isPending}
                    >
                      {t('clinical:actions.cancel')}
                    </button>
                    <button
                      onClick={handleAddTreatment}
                      className="btn-primary"
                      disabled={!treatmentId || quantity <= 0 || addTreatment.isPending}
                    >
                      {addTreatment.isPending ? t('clinical:actions.adding') : t('clinical:actions.add')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Finalize Encounter Modal */}
          {showFinalizeModal && (
            <div
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0,0,0,0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
              }}
              onClick={() => setShowFinalizeModal(false)}
            >
              <div
                className="card"
                style={{ width: '500px', maxWidth: '90%' }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="card-header">
                  <h2>{t('clinical:modals.finalizeTitle')}</h2>
                </div>
                <div className="card-body">
                  <p style={{ marginBottom: '12px', fontWeight: 500, color: 'var(--warning)' }}>
                    {t('clinical:modals.finalizeWarning')}
                  </p>
                  <p style={{ marginBottom: '12px', color: 'var(--gray-700)' }}>
                    {t('clinical:modals.finalizeDescription')}
                  </p>
                  <p style={{ marginBottom: '16px', color: 'var(--error)', fontWeight: 500 }}>
                    {t('clinical:modals.finalizeIrreversible')}
                  </p>

                  <div className="flex gap-2 justify-between">
                    <button
                      onClick={() => setShowFinalizeModal(false)}
                      className="btn-secondary"
                      disabled={finalize.isPending}
                    >
                      {t('clinical:actions.cancel')}
                    </button>
                    <button
                      onClick={handleFinalize}
                      className="btn-primary"
                      disabled={finalize.isPending}
                    >
                      {finalize.isPending ? t('clinical:actions.finalizing') : t('clinical:modals.confirmFinalize')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </RBACGuard>
    </AppLayout>
  );
}
