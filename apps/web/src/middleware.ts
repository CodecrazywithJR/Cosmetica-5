import createMiddleware from 'next-intl/middleware';
 
export default createMiddleware({
  // A list of all locales that are supported
  locales: ['en', 'ru', 'fr', 'uk', 'hy', 'es'],
 
  // Used when no locale matches
  defaultLocale: 'en',
  
  // Always use locale prefix
  localePrefix: 'always'
});
 
export const config = {
  // Match all pathnames except api routes and static files
  // This will handle / and legacy routes like /login, /agenda, /encounters, /proposals
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)']
};
