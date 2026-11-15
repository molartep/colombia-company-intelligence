import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Search } from './pages/Search'
import { CompanyProfile } from './pages/CompanyProfile'
import { Parameters } from './pages/Parameters'
import { SiteHeader } from './components/SiteHeader'
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
        <SiteHeader />
        <main id="main">
          <Routes>
            <Route path="/parameters" element={<Parameters />} />
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
          <span>Colombia Company Intelligence</span>
        </footer>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
