/**
 * Proposals Page
 * List of Clinical Charge Proposals (Reception workflow)
 * Fully internationalized with next-intl
 */

'use client';

import AppLayout from '@/components/layout/app-layout';
import { RBACGuard } from '@/components/rbac-guard';
import { ROLES } from '@/lib/auth-context';
import { useProposals, useConvertProposalToSale, useCancelProposal } from '@/lib/hooks/use-proposals';
import { useState, useMemo } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { ClinicalChargeProposal } from '@/lib/types';

export default function ProposalsPage() {
  const t = useTranslations('pos');
  const tCommon = useTranslations('common');
  const locale = useLocale();
  const [statusFilter, setStatusFilter] = useState<string>('draft');
  const { data, isLoading, error } = useProposals({ status: statusFilter || undefined });
  
  const convertToSale = useConvertProposalToSale();
  const cancelProposal = useCancelProposal();

  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);
  const [legalEntityId, setLegalEntityId] = useState('');
  const [cancellationReason, setCancellationReason] = useState('');
  const [showConvertModal, setShowConvertModal] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);

  // Date formatter using current language
  const dateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      }),
    [locale]
  );

  // Currency formatter using current language
  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'EUR',
      }),
    [locale]
  );

  const handleConvertToSale = async () => {
    if (!selectedProposalId || !legalEntityId) return;
    
    try {
      await convertToSale.mutateAsync({ proposalId: selectedProposalId, legalEntityId });
      setShowConvertModal(false);
      setSelectedProposalId(null);
      setLegalEntityId('');
    } catch (err) {
      console.error('Error converting proposal:', err);
    }
  };

  const handleCancelProposal = async () => {
    if (!selectedProposalId || !cancellationReason) return;
    
    try {
      await cancelProposal.mutateAsync({ id: selectedProposalId, cancellationReason });
      setShowCancelModal(false);
      setSelectedProposalId(null);
      setCancellationReason('');
    } catch (err) {
      console.error('Error cancelling proposal:', err);
    }
  };

  const openConvertModal = (proposal: ClinicalChargeProposal) => {
    setSelectedProposalId(proposal.id);
    setShowConvertModal(true);
  };

  const openCancelModal = (proposal: ClinicalChargeProposal) => {
    setSelectedProposalId(proposal.id);
    setShowCancelModal(true);
  };

  return (
    <AppLayout>
      <RBACGuard roles={[ROLES.ADMIN, ROLES.RECEPTION, ROLES.CLINICAL_OPS, ROLES.ACCOUNTING]}>
        <div>
          <div className="page-header">
            <h1>{t('pos:title')}</h1>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ padding: '8px 12px', border: '1px solid var(--gray-300)', borderRadius: '6px' }}
              aria-label={t('pos:filters.status')}
            >
              <option value="">{t('pos:filters.allStatuses')}</option>
              <option value="draft">{t('pos:proposal.status.draft')}</option>
              <option value="converted">{t('pos:proposal.status.converted')}</option>
              <option value="cancelled">{t('pos:proposal.status.cancelled')}</option>
            </select>
          </div>

          {error && (
            <div className="alert-error">
              {t('pos:errors.loadingFailed')}: {(error as any)?.message || t('common:errors.generic')}
            </div>
          )}

          {isLoading ? (
            <div className="card">
              <div className="card-body">{t('common:status.loading')}</div>
            </div>
          ) : (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>{t('pos:table.date')}</th>
                    <th>{t('pos:table.patient')}</th>
                    <th>{t('pos:table.practitioner')}</th>
                    <th>{t('pos:table.items')}</th>
                    <th>{t('pos:table.total')}</th>
                    <th>{t('pos:table.status')}</th>
                    <th>{t('pos:table.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.results.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '32px' }}>
                        {t('pos:empty.noProposals')}
                      </td>
                    </tr>
                  ) : (
                    data?.results.map((proposal) => (
                      <tr key={proposal.id}>
                        <td>{dateFormatter.format(new Date(proposal.created_at))}</td>
                        <td>
                          <div style={{ fontWeight: 500 }}>{proposal.patient.full_name}</div>
                          <div style={{ fontSize: '12px', color: 'var(--gray-600)' }}>
                            {proposal.patient.email}
                          </div>
                        </td>
                        <td>{proposal.practitioner.display_name}</td>
                        <td>
                          {t('pos:labels.items_other', { count: proposal.lines.length })}
                        </td>
                        <td style={{ fontWeight: 500 }}>
                          {currencyFormatter.format(Number(proposal.total_amount))}
                        </td>
                        <td>
                          <span className={`badge badge-${proposal.status}`}>
                            {t(`pos:proposal.status.${proposal.status}`, proposal.status)}
                          </span>
                        </td>
                        <td>
                          <div className="flex gap-2">
                            {proposal.status === 'draft' && (
                              <>
                                <button
                                  onClick={() => openConvertModal(proposal)}
                                  className="btn-primary btn-sm"
                                >
                                  {t('pos:actions.createSale')}
                                </button>
                                <button
                                  onClick={() => openCancelModal(proposal)}
                                  className="btn-secondary btn-sm"
                                  style={{ color: 'var(--error)' }}
                                >
                                  {t('pos:actions.cancel')}
                                </button>
                              </>
                            )}
                            {proposal.status === 'converted' && proposal.converted_to_sale_id && (
                              <a
                                href={`/sales/${proposal.converted_to_sale_id}`}
                                className="btn-secondary btn-sm"
                                style={{ textDecoration: 'none' }}
                              >
                                {t('pos:actions.viewSale')}
                              </a>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {data && data.results.length > 0 && (
            <div style={{ marginTop: '16px', fontSize: '14px', color: 'var(--gray-600)' }}>
              {t('pos:summary.totalProposals')}: {data.count}
            </div>
          )}

          {/* Convert to Sale Modal */}
          {showConvertModal && (
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
              onClick={() => setShowConvertModal(false)}
            >
              <div
                className="card"
                style={{ width: '500px', maxWidth: '90%' }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="card-header">
                  <h2>{t('pos:modals.convertTitle')}</h2>
                </div>
                <div className="card-body">
                  <p style={{ marginBottom: '16px', color: 'var(--gray-700)' }}>
                    {t('pos:modals.convertDescription')}
                  </p>
                  
                  <div className="form-group">
                    <label htmlFor="legalEntityId">{t('pos:modals.legalEntityLabel')}</label>
                    <input
                      id="legalEntityId"
                      type="text"
                      value={legalEntityId}
                      onChange={(e) => setLegalEntityId(e.target.value)}
                      placeholder={t('pos:modals.legalEntityPlaceholder')}
                      required
                    />
                    <div style={{ fontSize: '12px', color: 'var(--gray-600)', marginTop: '4px' }}>
                      {t('pos:modals.legalEntityHelp')}
                    </div>
                  </div>

                  <div className="flex gap-2 justify-between">
                    <button
                      onClick={() => setShowConvertModal(false)}
                      className="btn-secondary"
                      disabled={convertToSale.isPending}
                    >
                      {t('pos:actions.cancel')}
                    </button>
                    <button
                      onClick={handleConvertToSale}
                      className="btn-primary"
                      disabled={!legalEntityId || convertToSale.isPending}
                    >
                      {convertToSale.isPending ? t('pos:actions.converting') : t('pos:actions.createSale')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Cancel Proposal Modal */}
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
                  <h2>{t('pos:modals.cancelTitle')}</h2>
                </div>
                <div className="card-body">
                  <p style={{ marginBottom: '16px', color: 'var(--error)', fontWeight: 500 }}>
                    {t('pos:modals.cancelDescription')}
                  </p>
                  
                  <div className="form-group">
                    <label htmlFor="cancellationReason">{t('pos:modals.cancellationReasonLabel')}</label>
                    <textarea
                      id="cancellationReason"
                      value={cancellationReason}
                      onChange={(e) => setCancellationReason(e.target.value)}
                      placeholder={t('pos:modals.cancellationReasonPlaceholder')}
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
                      {t('pos:actions.back')}
                    </button>
                    <button
                      onClick={handleCancelProposal}
                      className="btn-destructive"
                      disabled={!cancellationReason || cancelProposal.isPending}
                    >
                      {cancelProposal.isPending ? t('pos:actions.cancelling') : t('pos:modals.confirmCancel')}
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
