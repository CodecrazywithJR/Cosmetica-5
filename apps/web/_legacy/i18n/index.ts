/**
 * i18n Configuration
 * Internationalization setup with i18next + react-i18next
 * 
 * Supported languages: ru (default), uk, hy, fr, es
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Import locale files
import ruCommon from './locales/ru/common.json';
import ukCommon from './locales/uk/common.json';
import hyCommon from './locales/hy/common.json';
import frCommon from './locales/fr/common.json';
import esCommon from './locales/es/common.json';

import ruAgenda from './locales/ru/agenda.json';
import ukAgenda from './locales/uk/agenda.json';
import hyAgenda from './locales/hy/agenda.json';
import frAgenda from './locales/fr/agenda.json';
import esAgenda from './locales/es/agenda.json';

import ruPos from './locales/ru/pos.json';
import ukPos from './locales/uk/pos.json';
import hyPos from './locales/hy/pos.json';
import frPos from './locales/fr/pos.json';
import esPos from './locales/es/pos.json';

import ruClinical from './locales/ru/clinical.json';
import ukClinical from './locales/uk/clinical.json';
import hyClinical from './locales/hy/clinical.json';
import frClinical from './locales/fr/clinical.json';
import esClinical from './locales/es/clinical.json';

// Supported languages
export const SUPPORTED_LANGUAGES = ['ru', 'uk', 'hy', 'fr', 'es'] as const;
export type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number];

export const DEFAULT_LANGUAGE: SupportedLanguage = 'ru';

// Language labels for UI
export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  ru: 'Русский',
  uk: 'Українська',
  hy: 'Հայերեն',
  fr: 'Français',
  es: 'Español',
};

// Get saved language from localStorage or fallback to default
function getSavedLanguage(): SupportedLanguage {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE;
  
  const saved = localStorage.getItem('preferred_language');
  if (saved && SUPPORTED_LANGUAGES.includes(saved as SupportedLanguage)) {
    return saved as SupportedLanguage;
  }
  return DEFAULT_LANGUAGE;
}

// Initialize i18next
i18n
  .use(initReactI18next) // Pass i18n instance to react-i18next
  .init({
    resources: {
      ru: { common: ruCommon, agenda: ruAgenda, pos: ruPos, clinical: ruClinical },
      uk: { common: ukCommon, agenda: ukAgenda, pos: ukPos, clinical: ukClinical },
      hy: { common: hyCommon, agenda: hyAgenda, pos: hyPos, clinical: hyClinical },
      fr: { common: frCommon, agenda: frAgenda, pos: frPos, clinical: frClinical },
      es: { common: esCommon, agenda: esAgenda, pos: esPos, clinical: esClinical },
    },
    lng: getSavedLanguage(),
    fallbackLng: DEFAULT_LANGUAGE,
    defaultNS: 'common',
    ns: ['common', 'agenda', 'pos', 'clinical'],
    
    interpolation: {
      escapeValue: false, // React already escapes values
    },

    react: {
      useSuspense: false, // Disable suspense to avoid SSR issues
    },
  });

// Save language preference when changed
i18n.on('languageChanged', (lng) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('preferred_language', lng);
  }
});

export default i18n;
