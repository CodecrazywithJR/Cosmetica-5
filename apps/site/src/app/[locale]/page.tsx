'use client';

import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { contentAPI, WebsiteSettings, Service } from '@/lib/api';

export default function HomePage() {
  const t = useTranslations();
  const params = useParams();
  const locale = params.locale as string;

  const [settings, setSettings] = useState<WebsiteSettings | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [settingsData, servicesData] = await Promise.all([
          contentAPI.getSettings(),
          contentAPI.getServices(locale),
        ]);
        setSettings(settingsData);
        setServices(servicesData);
      } catch (err) {
        console.error('Error loading data:', err);
        setError(t('common.error'));
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [locale, t]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl">{t('common.loading')}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <div className="flex-shrink-0">
              <h1 className="text-2xl font-bold text-primary">
                {settings?.clinic_name || 'DermaClinic'}
              </h1>
            </div>
            <div className="flex space-x-8">
              <Link href={`/${locale}`} className="text-gray-900 hover:text-primary">
                {t('nav.home')}
              </Link>
              <Link href={`/${locale}/services`} className="text-gray-700 hover:text-primary">
                {t('nav.services')}
              </Link>
              <Link href={`/${locale}/team`} className="text-gray-700 hover:text-primary">
                {t('nav.team')}
              </Link>
              <Link href={`/${locale}/blog`} className="text-gray-700 hover:text-primary">
                {t('nav.blog')}
              </Link>
              <Link href={`/${locale}/contact`} className="text-gray-700 hover:text-primary">
                {t('nav.contact')}
              </Link>
            </div>
            <div className="flex space-x-2">
              {settings?.enabled_languages?.map((lang) => (
                <Link
                  key={lang}
                  href={`/${lang}`}
                  className={`px-2 py-1 rounded ${
                    locale === lang ? 'bg-primary text-white' : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {lang.toUpperCase()}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="bg-gradient-to-r from-primary to-secondary text-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-5xl font-bold mb-4">{t('home.hero.title')}</h2>
          <p className="text-xl mb-8">{t('home.hero.subtitle')}</p>
          <Link
            href={`/${locale}/contact`}
            className="inline-block bg-white text-primary px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition"
          >
            {t('home.hero.cta')}
          </Link>
        </div>
      </section>

      {/* Services Section */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-12">{t('home.services.title')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {services.slice(0, 6).map((service) => (
              <div key={service.id} className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition">
                <h3 className="text-xl font-semibold mb-2">{service.name}</h3>
                <p className="text-gray-600 mb-4">{service.description}</p>
                {service.price && (
                  <p className="text-primary font-bold">€{service.price}</p>
                )}
                {service.duration_minutes && (
                  <p className="text-gray-500 text-sm">{service.duration_minutes} min</p>
                )}
              </div>
            ))}
          </div>
          <div className="text-center mt-8">
            <Link
              href={`/${locale}/services`}
              className="text-primary font-semibold hover:underline"
            >
              {t('home.services.viewAll')} →
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
              <h3 className="text-lg font-semibold mb-4">{settings?.clinic_name}</h3>
              <p className="text-gray-400">{settings?.address}</p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-4">{t('nav.contact')}</h3>
              <p className="text-gray-400">{settings?.phone}</p>
              <p className="text-gray-400">{settings?.email}</p>
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-4">Social</h3>
              <div className="flex space-x-4">
                {settings?.instagram_url && (
                  <a href={settings.instagram_url} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white">
                    Instagram
                  </a>
                )}
                {settings?.facebook_url && (
                  <a href={settings.facebook_url} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-white">
                    Facebook
                  </a>
                )}
              </div>
            </div>
          </div>
          <div className="mt-8 text-center text-gray-400">
            <p>&copy; {new Date().getFullYear()} {settings?.clinic_name}. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
