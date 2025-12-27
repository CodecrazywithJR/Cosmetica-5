'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useAuth } from '@/lib/auth-context';
import { routes, type Locale } from '@/lib/routing';
import apiClient from '@/lib/api-client';

export default function MustChangePasswordPage({ params: { locale } }: { params: { locale: string } }) {
  const router = useRouter();
  const { user, logout } = useAuth();
  const t = useTranslations('auth');
  const tCommon = useTranslations('common');

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if user doesn't need to change password
  useEffect(() => {
    if (!user?.must_change_password) {
      router.push(routes.home(locale as Locale));
    }
  }, [user, locale, router]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!currentPassword) {
      newErrors.currentPassword = t('changePassword.currentPasswordRequired');
    }

    if (!newPassword) {
      newErrors.newPassword = t('changePassword.newPasswordRequired');
    } else if (newPassword.length < 8 || newPassword.length > 16) {
      newErrors.newPassword = t('changePassword.passwordLength');
    }

    if (!confirmPassword) {
      newErrors.confirmPassword = t('changePassword.confirmPasswordRequired');
    } else if (newPassword !== confirmPassword) {
      newErrors.confirmPassword = t('changePassword.passwordMismatch');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      await apiClient.post('/api/v1/users/me/change-password/', {
        current_password: currentPassword,
        new_password: newPassword,
      });

      // Password changed successfully - redirect to home
      router.push(routes.home(locale as Locale));
    } catch (error: any) {
      if (error.response?.data) {
        const apiErrors = error.response.data;
        const newErrors: Record<string, string> = {};

        // Map API errors
        Object.keys(apiErrors).forEach((key) => {
          const errorMessage = Array.isArray(apiErrors[key])
            ? apiErrors[key][0]
            : apiErrors[key];
          
          if (key === 'current_password') {
            newErrors.currentPassword = errorMessage;
          } else if (key === 'new_password') {
            newErrors.newPassword = errorMessage;
          } else {
            newErrors.general = errorMessage;
          }
        });

        setErrors(newErrors);
      } else {
        setErrors({ general: t('changePassword.error') });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    logout();
  };

  if (!user?.must_change_password) {
    return null; // Will redirect in useEffect
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h2 className="mt-6 text-center text-3xl font-bold text-gray-900">
          {t('changePassword.title')}
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600">
          {t('changePassword.description')}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          {/* Warning Banner */}
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded">
            <p className="text-sm text-yellow-800">
              ⚠️ {t('changePassword.mandatoryWarning')}
            </p>
          </div>

          {/* General Error */}
          {errors.general && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded text-red-700">
              {errors.general}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Current Password */}
            <div>
              <label htmlFor="current_password" className="block text-sm font-medium text-gray-700">
                {t('changePassword.currentPassword')} <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                id="current_password"
                value={currentPassword}
                onChange={(e) => {
                  setCurrentPassword(e.target.value);
                  if (errors.currentPassword) {
                    setErrors((prev) => {
                      const newErrors = { ...prev };
                      delete newErrors.currentPassword;
                      return newErrors;
                    });
                  }
                }}
                className={`mt-1 block w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 ${
                  errors.currentPassword ? 'border-red-500' : 'border-gray-300'
                }`}
                disabled={isSubmitting}
              />
              {errors.currentPassword && (
                <p className="mt-1 text-sm text-red-600">{errors.currentPassword}</p>
              )}
            </div>

            {/* New Password */}
            <div>
              <label htmlFor="new_password" className="block text-sm font-medium text-gray-700">
                {t('changePassword.newPassword')} <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                id="new_password"
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value);
                  if (errors.newPassword) {
                    setErrors((prev) => {
                      const newErrors = { ...prev };
                      delete newErrors.newPassword;
                      return newErrors;
                    });
                  }
                }}
                className={`mt-1 block w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 ${
                  errors.newPassword ? 'border-red-500' : 'border-gray-300'
                }`}
                disabled={isSubmitting}
                placeholder={t('changePassword.passwordLength')}
              />
              {errors.newPassword && (
                <p className="mt-1 text-sm text-red-600">{errors.newPassword}</p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirm_password" className="block text-sm font-medium text-gray-700">
                {t('changePassword.confirmPassword')} <span className="text-red-500">*</span>
              </label>
              <input
                type="password"
                id="confirm_password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  if (errors.confirmPassword) {
                    setErrors((prev) => {
                      const newErrors = { ...prev };
                      delete newErrors.confirmPassword;
                      return newErrors;
                    });
                  }
                }}
                className={`mt-1 block w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 ${
                  errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                }`}
                disabled={isSubmitting}
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>
              )}
            </div>

            {/* Submit Button */}
            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400"
              >
                {isSubmitting ? tCommon('actions.saving') : t('changePassword.submit')}
              </button>
            </div>

            {/* Logout Link */}
            <div className="text-center">
              <button
                type="button"
                onClick={handleLogout}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                {t('changePassword.logout')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
