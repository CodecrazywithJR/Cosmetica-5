/**
 * Language Switcher Component
 * Dropdown for selecting UI language (en, ru, uk, hy, fr, es)
 * Uses next-intl routing to switch locales
 */

'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter, usePathname } from 'next/navigation';

const SUPPORTED_LOCALES = ['en', 'ru', 'fr', 'uk', 'hy', 'es'] as const;
type SupportedLocale = typeof SUPPORTED_LOCALES[number];

const LOCALE_LABELS: Record<SupportedLocale, string> = {
  en: 'English',
  ru: 'Русский',
  uk: 'Українська',
  hy: 'Հայերեն',
  fr: 'Français',
  es: 'Español',
};

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations('common');

  const handleLanguageChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newLocale = event.target.value as SupportedLocale;
    
    // Extract the path without the locale prefix
    const pathWithoutLocale = pathname.replace(`/${locale}`, '');
    
    // Navigate to the same path with new locale
    router.push(`/${newLocale}${pathWithoutLocale || ''}`);
  };

  return (
    <div className="language-switcher">
      <label htmlFor="language-select" className="language-label">
        {t('languageLabel')}
      </label>
      <select
        id="language-select"
        value={locale}
        onChange={handleLanguageChange}
        className="language-select"
      >
        {SUPPORTED_LOCALES.map((lang) => (
          <option key={lang} value={lang}>
            {LOCALE_LABELS[lang]}
          </option>
        ))}
      </select>
    </div>
  );
}
