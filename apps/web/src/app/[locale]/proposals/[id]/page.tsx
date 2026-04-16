/**
 * Proposal Detail Page
 * View proposal data + state-machine actions (FASE 2B)
 *
 * Buttons by state:
 *  - draft   → Send
 *  - sent    → Accept + Cancel
 *  - accepted / cancelled / expired → read-only
 */

'use client';

import AppLayout from '@/components/layout/app-layout';
import { RBACGuard } from '@/components/rbac-guard';
import { ROLES } from '@/lib/auth-context';
import {
  useProposal,
  useSendProposal,
  useAcceptProposal,
  useCancelProposal,
} from '@/lib/hooks/use-proposals';
import { useParams, useRouter } from 'next/navigation';
import { useState, useMemo } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { routes, type Locale } from '@/lib/routing';

export default function ProposalDetailPage() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('proposals');
  const tCommon = useTranslations('common');

  const proposalId = params.id as string;
  const { data: proposal, isLoading, error } = useProposal(proposalId);

  const sendProposal = useSendProposal();
  const acceptProposal = useAcceptProposal();
  const cancelProposal = useCancelProposal();

  // Accept modal state
  const [showAcceptModal, setShowAcceptModal] = useState(false);
  const [legalEntityId, setLegalEntityId] = useState('');

  // Cancel modal state
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancellationReason, setCancellationReason] = useState('');

  // Formatters
  const dateFormatter = useMemo(
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

  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'EUR',
      }),
    [locale]
  );

  // ---------- Handlers ----------

  const handleSend = async () => {
    try {
      await sendProposal.mutateAsync({ id: proposalId });
    } catch (err) {
      console.error('Error sending proposal:', err);
    }
  };

  const handleAccept = async () => {
    if (!legalEntityId) return;
    try {
      await acceptProposal.mutateAsync({ id: proposalId, legalEntityId });
      setShowAcceptModal(false);
      setLegalEntityId('');
    } catch (err) {
      console.error('Error accepting proposal:', err);
    }
  };

  const handleCancel = async () => {
    if (!cancellationReason) return;
    try {
      await cancelProposal.mutateAsync({ id: proposalId, cancellationReason });
      setShowCancelModal(false);
      setCancellationReason('');
    } catch (err) {
      console.error('Error cancelling proposal:', err);
    }
  };

  // ---------- Loading / Error guards ----------

  if (isLoading) {
    return (
      <AppLayout>
        <div className="card">
          <div className="card-body">{tCommon('status.loading')}</div>
        </div>
      </AppLayout>
    );
  }

  if (error || !proposal) {
    return (
      <AppLayout>
        <div className="card">
          <div className="card-body">
            <p>{t('errors.loadFailed')}</p>
            <button className="btn-secondary" onClick={() => router.push(routes.proposals.list(locale))}>
              {t('actions.backToList')}
            </button>
          </div>
        </div>
      </AppLayout>
    );
  }

  // ---------- Status badge helper ----------

  const statusBadge = (s: string) => (
    <span className={`badge badge-${s}`}>{t(`status.${s}` as any)}</span>
  );

  // ---------- Render ----------

  return (
    <AppLayout>
      <RBACGuard roles={[ROLES.ADMIN, ROLES.RECEPTION, ROLES.PRACTITIONER, ROLES.ACCOUNTING]}>
        <div>
          {/* Header */}
          <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <button
                className="btn-secondary btn-sm"
                onClick={() => router.push(routes.proposals.list(locale))}
                style={{ marginBottom: '8px' }}
              >
                ← {t('actions.backToList')}
              </button>
              <h1 style={{ margin: 0 }}>{t('detail.title')}</h1>
            </div>
            <div>{statusBadge(proposal.status)}</div>
          </div>

          {/* Proposal Info */}
          <div className="card" style={{ marginBottom: '16px' }}>
            <div className="card-header">
              <h2>{t('detail.info')}</h2>
            </div>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <strong>{t('detail.patient')}:</strong>{' '}
                  {proposal.patient?.full_name || '—'}
                </div>
                <div>
                  <strong>{t('detail.practitioner')}:</strong>{' '}
                  {proposal.practitioner?.display_name || '—'}
                </div>
                <div>
                  <strong>{t('detail.created')}:</strong>{' '}
                  {proposal.created_at ? dateFormatter.format(new Date(proposal.created_at)) : '—'}
                </div>
                <div>
                  <strong>{t('detail.validUntil')}:</strong>{' '}
                  {proposal.valid_until ? dateFormatter.format(new Date(proposal.valid_until)) : '—'}
                </div>
                {proposal.sent_at && (
                  <div>
                    <strong>{t('detail.sentAt')}:</strong>{' '}
                    {dateFormatter.format(new Date(proposal.sent_at))}
                  </div>
                )}
                {proposal.accepted_at && (
                  <div>
                    <strong>{t('detail.acceptedAt')}:</strong>{' '}
                    {dateFormatter.format(new Date(proposal.accepted_at))}
                  </div>
                )}
                {proposal.cancellation_reason && (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <strong>{t('detail.cancellationReason')}:</strong>{' '}
                    {proposal.cancellation_reason}
                  </div>
                )}
                {proposal.notes && (
                  <div style={{ gridColumn: '1 / -1' }}>
                    <strong>{t('detail.notes')}:</strong>{' '}
                    {proposal.notes}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Lines Table */}
          <div className="card" style={{ marginBottom: '16px' }}>
            <div className="card-header">
              <h2>{t('detail.lines')}</h2>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>{t('detail.treatmentName')}</th>
                    <th style={{ textAlign: 'center' }}>{t('detail.quantity')}</th>
                    <th style={{ textAlign: 'right' }}>{t('detail.unitPrice')}</th>
                    <th style={{ textAlign: 'right' }}>{t('detail.lineTotal')}</th>
                  </tr>
                </thead>
                <tbody>
                  {proposal.lines && proposal.lines.length > 0 ? (
                    proposal.lines.map((line: any) => (
                      <tr key={line.id}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{line.treatment_name}</div>
                          {line.description && (
                            <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                              {line.description}
                            </div>
                          )}
                        </td>
                        <td style={{ textAlign: 'center' }}>{line.quantity}</td>
                        <td style={{ textAlign: 'right' }}>
                          {currencyFormatter.format(Number(line.unit_price))}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 500 }}>
                          {currencyFormatter.format(Number(line.line_total))}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} style={{ textAlign: 'center', padding: '24px' }}>
                        {t('detail.noLines')}
                      </td>
                    </tr>
                  )}
                </tbody>
                {proposal.lines && proposal.lines.length > 0 && (
                  <tfoot>
                    <tr>
                      <td colSpan={3} style={{ textAlign: 'right', fontWeight: 700 }}>
                        {t('detail.total')}
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 700, fontSize: '16px' }}>
                        {currencyFormatter.format(Number(proposal.total_amount))}
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="card">
            <div className="card-body">
              <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                {/* DRAFT → Send */}
                {proposal.status === 'draft' && (
                  <button
                    className="btn-primary"
                    onClick={handleSend}
                    disabled={sendProposal.isPending}
                  >
                    {sendProposal.isPending ? t('actions.sending') : t('actions.send')}
                  </button>
                )}

                {/* SENT → Accept + Cancel */}
                {proposal.status === 'sent' && (
                  <>
                    <button
                      className="btn-primary"
                      onClick={() => setShowAcceptModal(true)}
                      disabled={acceptProposal.isPending}
                    >
                      {t('actions.accept')}
                    </button>
                    <button
                      className="btn-secondary"
                      onClick={() => setShowCancelModal(true)}
                      disabled={cancelProposal.isPending}
                      style={{ color: 'var(--error)' }}
                    >
                      {t('actions.cancel')}
                    </button>
                  </>
                )}

                {/* DRAFT → Cancel */}
                {proposal.status === 'draft' && (
                  <button
                    className="btn-secondary"
                    onClick={() => setShowCancelModal(true)}
                    disabled={cancelProposal.isPending}
                    style={{ color: 'var(--error)' }}
                  >
                    {t('actions.cancel')}
                  </button>
                )}

                {/* ACCEPTED → links */}
                {proposal.status === 'accepted' && proposal.converted_to_sale_id && (
                  <p style={{ margin: 0, color: 'var(--gray-600)' }}>
                    {t('detail.saleCreated')}: {proposal.converted_to_sale_id}
                  </p>
                )}

                {/* CANCELLED / EXPIRED → readonly info */}
                {(proposal.status === 'cancelled' || proposal.status === 'expired') && (
                  <p style={{ margin: 0, color: 'var(--gray-600)' }}>
                    {t(`detail.readonlyMessage.${proposal.status}`)}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Accept Modal */}
          {showAcceptModal && (
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
              onClick={() => setShowAcceptModal(false)}
            >
              <div
                className="card"
                style={{ width: '500px', maxWidth: '90%' }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="card-header">
                  <h2>{t('modals.acceptTitle')}</h2>
                </div>
                <div className="card-body">
                  <p style={{ marginBottom: '16px', color: 'var(--gray-700)' }}>
                    {t('modals.acceptDescription')}
                  </p>

                  <div className="form-group">
                    <label htmlFor="legalEntityId">{t('modals.legalEntityLabel')}</label>
                    <input
                      id="legalEntityId"
                      type="text"
                      value={legalEntityId}
                      onChange={(e) => setLegalEntityId(e.target.value)}
                      placeholder={t('modals.legalEntityPlaceholder')}
                      required
                    />
                  </div>

                  <div className="flex gap-2 justify-between">
                    <button
                      onClick={() => setShowAcceptModal(false)}
                      className="btn-secondary"
                      disabled={acceptProposal.isPending}
                    >
                      {t('actions.back')}
                    </button>
                    <button
                      onClick={handleAccept}
                      className="btn-primary"
                      disabled={!legalEntityId || acceptProposal.isPending}
                    >
                      {acceptProposal.isPending ? t('actions.accepting') : t('actions.confirmAccept')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Cancel Modal */}
          {showCancelModal && (
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
              onClick={() => setShowCancelModal(false)}
            >
              <div
                className="card"
                style={{ width: '500px', maxWidth: '90%' }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="card-header">
                  <h2>{t('modals.cancelTitle')}</h2>
                </div>
                <div className="card-body">
                  <p style={{ marginBottom: '16px', color: 'var(--error)', fontWeight: 500 }}>
                    {t('modals.cancelDescription')}
                  </p>

                  <div className="form-group">
                    <label htmlFor="cancellationReason">{t('modals.cancellationReasonLabel')}</label>
                    <textarea
                      id="cancellationReason"
                      value={cancellationReason}
                      onChange={(e) => setCancellationReason(e.target.value)}
                      placeholder={t('modals.cancellationReasonPlaceholder')}
                      required
                      rows={4}
                    />
                  </div>

                  <div className="flex gap-2 justify-between">
                    <button
                      onClick={() => setShowCancelModal(false)}
                      className="btn-secondary"
                      disabled={cancelProposal.isPending}
                    >
                      {t('actions.back')}
                    </button>
                    <button
                      onClick={handleCancel}
                      className="btn-destructive"
                      disabled={!cancellationReason || cancelProposal.isPending}
                    >
                      {cancelProposal.isPending ? t('actions.cancelling') : t('modals.confirmCancel')}
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
