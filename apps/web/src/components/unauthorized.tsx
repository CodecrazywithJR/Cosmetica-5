/**
 * Unauthorized Access Component
 * Shows 403 error when users without admin role try to access restricted sections
 */

'use client';

import React from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';
import { routes, type Locale } from '@/lib/routing';

export default function Unauthorized() {
  const t = useTranslations('users.unauthorized');
  const router = useRouter();
  const locale = useLocale() as Locale;

  return (
    <div className="unauthorized-container">
      <div className="unauthorized-content">
        <div className="error-code">403</div>
        <h1>{t('title')}</h1>
        <p>{t('description')}</p>
        <button
          onClick={() => router.push(routes.dashboard(locale))}
          className="btn-primary"
        >
          {t('action')}
        </button>
      </div>

      <style jsx>{`
        .unauthorized-container {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background-color: var(--color-background, #f5f5f5);
          padding: 20px;
        }

        .unauthorized-content {
          text-align: center;
          max-width: 500px;
        }

        .error-code {
          font-size: 96px;
          font-weight: 700;
          color: var(--color-error, #dc2626);
          line-height: 1;
          margin-bottom: 16px;
        }

        h1 {
          font-size: 28px;
          font-weight: 600;
          color: var(--color-text-primary, #111827);
          margin-bottom: 12px;
        }

        p {
          font-size: 16px;
          color: var(--color-text-secondary, #6b7280);
          margin-bottom: 32px;
          line-height: 1.6;
        }

        .btn-primary {
          padding: 12px 24px;
          background-color: var(--color-primary, #3b82f6);
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .btn-primary:hover {
          background-color: var(--color-primary-hover, #2563eb);
        }
      `}</style>
    </div>
  );
}
