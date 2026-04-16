/**
 * Legal Entity Selector — Superuser plane switching.
 *
 * Consumes GET /api/v1/system/legal-entities/?is_active=true
 * Shows a searchable list so the superuser can pick which tenant to operate in.
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import apiClient from '@/lib/api/api-client';
import { useActiveLegalEntity, type LegalEntitySummary } from '@/lib/active-legal-entity-context';
import { routes, type Locale } from '@/lib/routing';

interface LegalEntityAPIItem {
  id: string;
  legal_name: string;
  trade_name?: string | null;
  country_code?: string;
  city?: string | null;
  is_active?: boolean;
}

interface LegalEntityListResponse {
  count: number;
  results: LegalEntityAPIItem[];
}

interface LegalEntitySelectorProps {
  onClose?: () => void;
}

export default function LegalEntitySelector({ onClose }: LegalEntitySelectorProps) {
  const router = useRouter();
  const locale = useLocale() as Locale;
  const t = useTranslations('system');
  const tCommon = useTranslations('common');
  const { selectLegalEntity } = useActiveLegalEntity();

  const [entities, setEntities] = useState<LegalEntityAPIItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function fetchEntities() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.get<LegalEntityListResponse>(
          '/api/v1/system/legal-entities/',
          { params: { is_active: 'true' } },
        );
        if (!cancelled) {
          setEntities(data.results || []);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err?.message || 'Error');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchEntities();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return entities;
    const q = search.toLowerCase();
    return entities.filter(
      (e) =>
        e.legal_name.toLowerCase().includes(q) ||
        (e.trade_name && e.trade_name.toLowerCase().includes(q)) ||
        (e.city && e.city.toLowerCase().includes(q)) ||
        (e.country_code && e.country_code.toLowerCase().includes(q)),
    );
  }, [entities, search]);

  function handleSelect(entity: LegalEntityAPIItem) {
    const summary: LegalEntitySummary = {
      id: entity.id,
      legal_name: entity.legal_name,
      trade_name: entity.trade_name,
      country_code: entity.country_code,
      city: entity.city,
      is_active: entity.is_active,
    };
    selectLegalEntity(summary);
    onClose?.();
  }

  return (
    <div className="le-selector-overlay" onClick={onClose}>
      <div
        className="le-selector-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="le-selector-header">
          <h2>{t('selector.title')}</h2>
          {onClose && (
            <button
              className="le-selector-close"
              onClick={onClose}
              aria-label={tCommon('actions.close')}
            >
              ×
            </button>
          )}
        </div>

        <div className="le-selector-search">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('selector.search_placeholder')}
            autoFocus
          />
        </div>

        <div className="le-selector-list">
          {loading && (
            <div className="le-selector-loading">{tCommon('loading')}</div>
          )}

          {error && (
            <div className="le-selector-error">
              <p>{error}</p>
              <button className="btn-secondary" onClick={() => window.location.reload()}>
                {tCommon('retry')}
              </button>
            </div>
          )}

          {!loading && !error && filtered.length === 0 && (
            <div className="le-selector-empty">
              {entities.length === 0 ? (
                <>
                  <p style={{ marginBottom: 12 }}>{t('selector.no_results')}</p>
                  <button
                    className="btn-primary btn-sm"
                    onClick={() => {
                      onClose?.();
                      router.push(routes.legalEntities.create(locale));
                    }}
                    style={{ fontSize: 13, padding: '6px 16px' }}
                  >
                    {t('selector.create_first')}
                  </button>
                </>
              ) : (
                t('selector.no_results')
              )}
            </div>
          )}

          {!loading &&
            !error &&
            filtered.map((entity) => (
              <button
                key={entity.id}
                className="le-selector-item"
                onClick={() => handleSelect(entity)}
              >
                <div className="le-selector-item-name">
                  {entity.legal_name}
                </div>
                <div className="le-selector-item-meta">
                  {entity.trade_name && (
                    <span className="le-selector-item-trade">
                      {entity.trade_name}
                    </span>
                  )}
                  {entity.country_code && (
                    <span className="le-selector-item-country">
                      {entity.country_code}
                    </span>
                  )}
                  {entity.city && (
                    <span className="le-selector-item-city">
                      {entity.city}
                    </span>
                  )}
                </div>
              </button>
            ))}

          {/* Manage link — shown when entities exist */}
          {!loading && !error && entities.length > 0 && (
            <div style={{
              padding: '10px 16px',
              borderTop: '1px solid var(--gray-200, #e5e7eb)',
              textAlign: 'center',
            }}>
              <button
                className="btn-secondary btn-sm"
                onClick={() => {
                  onClose?.();
                  router.push(routes.legalEntities.list(locale));
                }}
                style={{ fontSize: 12, padding: '4px 14px' }}
              >
                {t('selector.manage')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
