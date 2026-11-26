import { lazy, Suspense } from 'react'
import { t, useLanguage } from './i18n'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { Search } from './pages/Search'
import { SiteHeader } from './components/SiteHeader'
import './styles.css'

// Keep search available immediately; load secondary pages on first navigation.
const CompanyProfile = lazy(() =>
  import('./pages/CompanyProfile').then((module) => ({ default: module.CompanyProfile })),
)
const Parameters = lazy(() =>
  import('./pages/Parameters').then((module) => ({ default: module.Parameters })),
)
const Advanced = lazy(() =>
  import('./pages/Advanced').then((module) => ({ default: module.Advanced })),
)
const RaePage = lazy(() =>
  import('./components/GovernmentInvolvement').then((module) => ({ default: module.RaePage })),
)

const client = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: false, refetchOnWindowFocus: false } },
})
export function App({ queryClient = client }: { queryClient?: QueryClient } = {}) {
  useLanguage()
  return (
    <>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <a className="skip-link" href="#main">
            {t('application.skipToContent')}
          </a>
          <SiteHeader />
          <main id="main" tabIndex={-1}>
            <Suspense
              fallback={
                <div className="notice" role="status">
                  {t('application.loadingPage')}
                </div>
              }
            >
              <Routes>
                <Route path="/methodology/rae" element={<RaePage />} />
                <Route path="/parameters" element={<Parameters />} />
                <Route path="/references" element={<Advanced />} />
                <Route path="/advanced" element={<Navigate to="/references" replace />} />
                <Route path="/" element={<Search />} />
                <Route path="/companies/:id" element={<CompanyProfile />} />
                <Route
                  path="*"
                  element={
                    <div className="empty">
                      <h1>{t('application.pageNotFound')}</h1>
                      <Link to="/">{t('application.returnToCompanySearch')}</Link>
                    </div>
                  }
                />
              </Routes>
            </Suspense>
          </main>
          <footer>
            <span>Colombia Company Intelligence</span>
          </footer>
        </BrowserRouter>
      </QueryClientProvider>
    </>
  )
}
