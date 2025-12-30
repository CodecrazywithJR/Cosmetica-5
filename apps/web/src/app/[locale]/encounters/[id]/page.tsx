/**
 * Encounter Detail Page
 * View/edit encounter with treatments (Practitioner workflow)
 * Fully internationalized with next-intl
 */

'use client';

import AppLayout from '@/components/layout/app-layout';

// Deterministic UI mapping for photo.kind
function mapPhotoKind(kind: string): 'before' | 'after' | 'progress' | 'other' {
// UI domain for photo kind (closed set)
export type PhotoKindUI = 'before' | 'after' | 'progress' | 'other';
const PHOTO_KIND_UI: PhotoKindUI[] = ['before', 'after', 'progress', 'other'];
// Deterministic mapping: only allow UI domain, everything else (including 'clinical') → 'other'
function mapPhotoKind(kind: unknown): PhotoKindUI {
  return PHOTO_KIND_UI.includes(kind as PhotoKindUI) ? (kind as PhotoKindUI) : 'other';
}
import { RBACGuard } from '@/components/rbac-guard';
import { ROLES } from '@/lib/auth-context';
import { useEncounter, useAddTreatment, useFinalizeEncounter } from '@/lib/hooks/use-encounters';
import { useUploadPhoto, useDeletePhoto, useUploadDocument, useDeleteDocument } from '@/lib/hooks/use-attachments';
import { safeExternalUrl } from '@/lib/safe-external-url';
import { useGenerateProposal } from '@/lib/hooks/use-proposals';
import { useParams, useRouter } from 'next/navigation';
import { useState, useMemo } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { routes, type Locale } from '@/lib/routing';

export default function EncounterDetailPage() {
  {/* Attachments (UX v1, real logic) */}
  <div className="card mb-4">
    <div className="card-header">
      <h2>{t('clinical:encounterLabels.attachments')}</h2>
    </div>
    <div className="card-body">
      {/* Clinical Photos */}
      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600 }}>{t('clinical:attachmentsLabels.clinicalPhotos')}</h3>
        {encounter.status === 'draft' && (
          <PhotoUploader encounterId={encounter.id} />
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 12 }}>
          {encounter.clinical_photos && encounter.clinical_photos.length > 0 ? (
            encounter.clinical_photos.map(photo => {
              const uiKind = mapPhotoKind(photo.kind);
              const uiKind: PhotoKindUI = mapPhotoKind(photo.kind);
              const safeUrl = safeExternalUrl(photo.url);
              if (!safeUrl) return null;
              return (
                <div key={photo.id} style={{ border: '1px solid #eee', borderRadius: 8, padding: 8, width: 160 }}>
                  <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{t(`clinical:photoKind.${uiKind}`)}</div>
                                    <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{t(`clinical:photoKind.${uiKind}`)}</div>
                  <a href={safeUrl} target="_blank" rel="noopener noreferrer">
                    <img src={safeUrl} alt={uiKind} style={{ width: '100%', borderRadius: 4 }} />
                  </a>
                  {encounter.status === 'draft' && (
                    <DeletePhotoButton photoId={photo.id} />
                  )}
                </div>
              );
            })
          ) : (
            <div style={{ color: 'var(--gray-500)' }}>{t('clinical:attachmentsMessages.noPhotos')}</div>
          )}
        </div>
      </div>
      {/* Documents */}
      <div>
        <h3 style={{ fontSize: 16, fontWeight: 600 }}>{t('clinical:attachmentsLabels.documents')}</h3>
        {encounter.status === 'draft' && (
          <DocumentUploader encounterId={encounter.id} />
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 12 }}>
          {encounter.documents && encounter.documents.length > 0 ? (
            encounter.documents.map(doc => (
              <div key={doc.id} style={{ border: '1px solid #eee', borderRadius: 8, padding: 8, width: 180 }}>
                <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{doc.name}</div>
                {safeExternalUrl(doc.url) ? (
                  <a href={safeExternalUrl(doc.url)!} target="_blank" rel="noopener noreferrer">
                    <div style={{ fontSize: 13, color: '#0070f3' }}>{t(`clinical:documentKind.${doc.kind}`, doc.kind)}</div>
                  </a>
                ) : (
                  <div style={{ color: 'var(--error)' }}>{t('clinical:attachmentsMessages.invalidUrl')}</div>
                )}
                {encounter.status === 'draft' && (
                  <DeleteDocumentButton docId={doc.id} />
                )}
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--gray-500)' }}>{t('clinical:attachmentsMessages.noDocuments')}</div>
          )}
        </div>
      </div>
    </div>
  </div>

// PhotoUploader: Uploads a clinical photo to the encounter
function PhotoUploader({ encounterId }: { encounterId: string }) {
  const t = useTranslations('clinical');
  const uploadPhoto = useUploadPhoto();
  const [uploading, setUploading] = useState(false);
  const [category, setCategory] = useState('other');
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    setUploading(true);
    try {
      await uploadPhoto.mutateAsync({ encounterId, file: e.target.files[0], category });
    } finally {
      setUploading(false);
    }
  };
  return (
    <div style={{ marginBottom: 8 }}>
      <select value={category} onChange={e => setCategory(e.target.value)} style={{ marginRight: 8 }}>
        <option value="before">{t('clinical:photoKind.before')}</option>
        <option value="after">{t('clinical:photoKind.after')}</option>
        <option value="progress">{t('clinical:photoKind.progress')}</option>
        <option value="other">{t('clinical:photoKind.other')}</option>
      </select>
      <input type="file" accept="image/*" onChange={handleUpload} disabled={uploading} />
    </div>
  );
}

// DeletePhotoButton: Deletes a clinical photo
function DeletePhotoButton({ photoId }: { photoId: string }) {
  const t = useTranslations('clinical');
  const deletePhoto = useDeletePhoto();
  return (
    <button
      className="btn-danger btn-xs mt-2"
      onClick={() => deletePhoto.mutate(photoId)}
      disabled={deletePhoto.isPending}
    >
      {t('clinical:actions.delete')}
    </button>
  );
}

// DocumentUploader: Uploads a document to the encounter
function DocumentUploader({ encounterId }: { encounterId: string }) {
  const t = useTranslations('clinical');
  const uploadDocument = useUploadDocument();
  const [uploading, setUploading] = useState(false);
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    setUploading(true);
    try {
      await uploadDocument.mutateAsync({ encounterId, file: e.target.files[0] });
    } finally {
      setUploading(false);
    }
  };
  return (
    <div style={{ marginBottom: 8 }}>
      <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt" onChange={handleUpload} disabled={uploading} />
    </div>
  );
}

// DeleteDocumentButton: Deletes a document
function DeleteDocumentButton({ docId }: { docId: string }) {
  const t = useTranslations('clinical');
  const deleteDocument = useDeleteDocument();
  return (
    <button
      className="btn-danger btn-xs mt-2"
      onClick={() => deleteDocument.mutate(docId)}
      disabled={deleteDocument.isPending}
    >
      {t('clinical:actions.delete')}
    </button>
  );
}
                          // Attachment uploader y delete handler (patrón ERP, sin lógica de comparación)
                          import { useState } from 'react';

                          function AttachmentUploader({ type, encounterId }: { type: 'photo' | 'document'; encounterId: string }) {
                            const t = useTranslations('clinical');
                            const [uploading, setUploading] = useState(false);

                            const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
                              if (!e.target.files || e.target.files.length === 0) return;
                              setUploading(true);
                              // Lógica real de subida omitida por confidencialidad, patrón ERP
                              setTimeout(() => setUploading(false), 1000);
                            };

                            return (
                              <div style={{ marginBottom: 8 }}>
                                <input type="file" accept={type === 'photo' ? 'image/*' : '.pdf,.doc,.docx,.xls,.xlsx,.txt'} onChange={handleUpload} disabled={uploading} />
                              </div>
                            );
                          }

                          function handleDeleteAttachment(type: 'photo' | 'document', id: string) {
                            // Lógica real de borrado omitida por confidencialidad, patrón ERP
                          }
                          {/* Charge Proposal (UX v1, solo visualización, read-only) */}
                          <div className="card mb-4">
                            <div className="card-header">
                              <h2>{t('clinical:encounterLabels.chargeProposal')}</h2>
                            </div>
                            <div className="card-body">
                              {encounter.status === 'finalized' && encounter.charge_proposal ? (
                                <div>
                                  <div style={{ marginBottom: 8 }}>
                                    <span className={`badge badge-${encounter.charge_proposal.status}`}>{t(`clinical:chargeProposal.status.${encounter.charge_proposal.status}`, encounter.charge_proposal.status)}</span>
                                  </div>
                                  <div style={{ marginBottom: 8 }}>
                                    <strong>{t('clinical:chargeProposalLabels.summary')}</strong>: {encounter.charge_proposal.summary}
                                  </div>
                                  <div style={{ marginBottom: 8 }}>
                                    <strong>{t('clinical:chargeProposalLabels.total')}</strong>: {encounter.charge_proposal.total_amount} {encounter.charge_proposal.currency}
                                  </div>
                                  {encounter.charge_proposal.sale_id && (
                                    <div style={{ marginBottom: 8 }}>
                                      <strong>{t('clinical:chargeProposalLabels.sale')}</strong>: {encounter.charge_proposal.sale_id}
                                    </div>
                                  )}
                                  <div style={{ marginBottom: 8 }}>
                                    <strong>{t('clinical:chargeProposalLabels.created')}</strong>: {encounter.charge_proposal.created_at}
                                  </div>
                                  {encounter.charge_proposal.converted_at && (
                                    <div style={{ marginBottom: 8 }}>
                                      <strong>{t('clinical:chargeProposalLabels.converted')}</strong>: {encounter.charge_proposal.converted_at}
                                    </div>
                                  )}
                                  {encounter.charge_proposal.cancelled_at && (
                                    <div style={{ marginBottom: 8 }}>
                                      <strong>{t('clinical:chargeProposalLabels.cancelled')}</strong>: {encounter.charge_proposal.cancelled_at}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div style={{ color: 'var(--gray-500)' }}>
                                  {t('clinical:chargeProposalMessages.notExists')}
                                </div>
                              )}
                            </div>
                          </div>
                  {/* Proposed Treatment (UX v1) */}
                  <div className="card mb-4">
                    <div className="card-header">
                      <h2>{t('clinical:encounterLabels.proposedTreatment')}</h2>
                    </div>
                    <div className="card-body">
                      {encounter.status === 'draft' ? (
                        <ProposedTreatmentEditor
                          value={encounter.proposed_treatment || ''}
                          encounterId={encounter.id}
                        />
                      ) : (
                        <div style={{ minHeight: 64, color: encounter.proposed_treatment ? 'inherit' : 'var(--gray-500)' }}>
                          {encounter.proposed_treatment || t('clinical:empty.noProposedTreatment')}
                        </div>
                      )}
                    </div>
                  </div>
          // Proposed Treatment Editor (solo draft, editable, patrón ERP)
          import { useUpdateEncounter } from '@/lib/hooks/use-encounters';
          import { useState } from 'react';

          function ProposedTreatmentEditor({ value, encounterId }: { value: string; encounterId: string }) {
            const t = useTranslations('clinical');
            const [localValue, setLocalValue] = useState(value);
            const updateEncounter = useUpdateEncounter();
            const [saving, setSaving] = useState(false);

            const handleBlur = async () => {
              if (localValue !== value) {
                setSaving(true);
                try {
                  await updateEncounter.mutateAsync({ id: encounterId, data: { proposed_treatment: localValue } });
                } finally {
                  setSaving(false);
                }
              }
            };

            return (
              <textarea
                className="form-textarea w-full"
                rows={4}
                value={localValue}
                onChange={e => setLocalValue(e.target.value)}
                onBlur={handleBlur}
                placeholder={t('clinical:encounterPlaceholders.proposedTreatment')}
                disabled={saving}
              />
            );
          }
          {/* Clinical Notes (UX v1) */}
          <div className="card mb-4">
            <div className="card-header">
              <h2>{t('clinical:encounterLabels.clinicalNotes')}</h2>
            </div>
            <div className="card-body">
              {encounter.status === 'draft' ? (
                <ClinicalNotesEditor
                  value={encounter.clinical_notes || ''}
                  encounterId={encounter.id}
                />
              ) : (
                <div style={{ minHeight: 64, color: encounter.clinical_notes ? 'inherit' : 'var(--gray-500)' }}>
                  {encounter.clinical_notes || t('clinical:empty.noClinicalNotes')}
                </div>
              )}
            </div>
          </div>
  // Clinical Notes Editor (solo draft, editable, patrón ERP)
  import { useUpdateEncounter } from '@/lib/hooks/use-encounters';
  import { useState } from 'react';

  function ClinicalNotesEditor({ value, encounterId }: { value: string; encounterId: string }) {
    const t = useTranslations('clinical');
    const [localValue, setLocalValue] = useState(value);
    const updateEncounter = useUpdateEncounter();
    const [saving, setSaving] = useState(false);

    const handleBlur = async () => {
      if (localValue !== value) {
        setSaving(true);
        try {
          await updateEncounter.mutateAsync({ id: encounterId, data: { clinical_notes: localValue } });
        } finally {
          setSaving(false);
        }
      }
    };

    return (
      <textarea
        className="form-textarea w-full"
        rows={4}
        value={localValue}
        onChange={e => setLocalValue(e.target.value)}
        onBlur={handleBlur}
        placeholder={t('clinical:encounterPlaceholders.clinicalNotes')}
        disabled={saving}
      />
    );
  }
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
        {/* Encounter Header (UX v1, no editable, no acciones) */}
        <div className="page-header" style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--gray-900)' }}>
              {encounter.patient?.full_name || `${encounter.patient?.first_name || ''} ${encounter.patient?.last_name || ''}`}
            </div>
            <div style={{ fontSize: 14, color: 'var(--gray-700)' }}>
              {dateTimeFormatter.format(new Date(encounter.occurred_at))}
            </div>
            <div>
              <span className={`badge badge-${encounter.status}`}>{t(`clinical:encounter.status.${encounter.status}`, encounter.status)}</span>
            </div>
          </div>
        </div>

        {/* Chief Complaint (UX v1) */}
        <div className="card mb-4">
          <div className="card-header">
            <h2>{t('clinical:encounterLabels.chiefComplaint')}</h2>
          </div>
          <div className="card-body">
            {encounter.status === 'draft' ? (
              <ChiefComplaintEditor
                value={encounter.chief_complaint || ''}
                encounterId={encounter.id}
              />
            ) : (
              <div style={{ minHeight: 64, color: encounter.chief_complaint ? 'inherit' : 'var(--gray-500)' }}>
                {encounter.chief_complaint || t('clinical:empty.noChiefComplaint')}
              </div>
            )}
          // Chief Complaint Editor (solo draft, editable, patrón ERP)
          import { useUpdateEncounter } from '@/lib/hooks/use-encounters';
          import { useState } from 'react';

          function ChiefComplaintEditor({ value, encounterId }: { value: string; encounterId: string }) {
            const t = useTranslations('clinical');
            const [localValue, setLocalValue] = useState(value);
            const updateEncounter = useUpdateEncounter();
            const [saving, setSaving] = useState(false);

            const handleBlur = async () => {
              if (localValue !== value) {
                setSaving(true);
                try {
                  await updateEncounter.mutateAsync({ id: encounterId, data: { chief_complaint: localValue } });
                } finally {
                  setSaving(false);
                }
              }
            };

            return (
              <textarea
                className="form-textarea w-full"
                rows={4}
                value={localValue}
                onChange={e => setLocalValue(e.target.value)}
                onBlur={handleBlur}
                placeholder={t('clinical:encounterPlaceholders.chiefComplaint')}
                disabled={saving}
              />
            );
          }
          </div>
        </div>
        {/* ...existing code... */

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
