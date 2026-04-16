'use client';

import React from 'react';
import { useTranslations } from 'next-intl';
import { useAuth, ROLES } from '@/lib/auth-context';
import Unauthorized from '@/components/unauthorized';

export default function EncountersPage() {
  const t = useTranslations();
  const { user, hasAnyRole } = useAuth();

  if (user && !hasAnyRole([ROLES.ADMIN, ROLES.PRACTITIONER])) {
    return <Unauthorized />;
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
      <h2 className="text-xl font-semibold text-gray-900 mb-2">
        {t('patient360.tabs.encounters')}
      </h2>
      <p className="text-gray-500">{t('patient360.comingSoon')}</p>
    </div>
  );
}
