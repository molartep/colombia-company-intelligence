import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Search } from './pages/Search'
import { CompanyProfile } from './pages/CompanyProfile'
import './styles.css'

const client = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: false, refetchOnWindowFocus: false } },
})
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="header">
          <Link to="/" className="brand">
            <span className="brand-icon" aria-hidden="true">
              ci<span>↗</span>
            </span>
            <span>
              COLOMBIA<span className="brand-sub">COMPANY INTELLIGENCE</span>
            </span>
          </Link>
          <div className="header-right">
            <span className="badge">PHASE 01 · IDENTITY</span>
            <a
              href="https://github.com/molartep/colombia-company-intelligence"
              target="_blank"
              rel="noreferrer"
            >
              GitHub ↗
            </a>
          </div>
        </header>
        <main id="main">
          <Routes>
            <Route path="/" element={<Search />} />
            <Route path="/companies/:id" element={<CompanyProfile />} />
            <Route
              path="*"
              element={
                <div className="empty">
                  <h1>Page not found</h1>
                  <Link to="/">Return to company search</Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer>
          <span>
            Colombia Company Intelligence <span className="muted">/ Open source</span>
          </span>
          <p>Public registration data is evidence, not a due-diligence conclusion.</p>
          <a href="https://www.datos.gov.co/d/c82u-588k" target="_blank" rel="noreferrer">
            Data: Confecámaras · CC BY-SA 4.0 ↗
          </a>
        </footer>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
