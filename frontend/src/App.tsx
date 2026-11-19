import { t, useLanguage } from './i18n'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { Search } from './pages/Search'
import { CompanyProfile } from './pages/CompanyProfile'
import { Parameters } from './pages/Parameters'
import { Advanced } from './pages/Advanced'
import { SiteHeader } from './components/SiteHeader'
import './styles.css'

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
          <main id="main">
            <Routes>
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
          </main>
          <footer>
            <span>Colombia Company Intelligence</span>
          </footer>
        </BrowserRouter>
      </QueryClientProvider>
    </>
  )
}
