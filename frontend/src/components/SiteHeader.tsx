import { Link, NavLink } from 'react-router-dom'

export function SiteHeader() {
  return (
    <header className="header">
      <Link to="/" className="brand" aria-label="Colombia Company Intelligence home">
        <img
          className="brand-logo"
          src="/colombia-network-logo.png"
          alt="Colombia outline made of connected yellow, blue and red dots"
          width="128"
          height="144"
        />
        <span>
          COLOMBIA<span className="brand-sub">COMPANY INTELLIGENCE</span>
        </span>
      </Link>
      <nav className="header-tabs" aria-label="Main navigation">
        <NavLink to="/" end>
          Search
        </NavLink>
        <NavLink to="/parameters">Parameters</NavLink>
        <NavLink to="/advanced">Advanced</NavLink>
      </nav>
      <nav className="social-links" aria-label="Social media">
        <a
          className="social-button"
          href="https://github.com/molartep"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Martin Olarte on GitHub"
          title="GitHub"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
            <path d="M12 .75a11.25 11.25 0 0 0-3.558 21.923c.563.103.77-.244.77-.542 0-.267-.01-.975-.015-1.914-3.13.68-3.79-1.508-3.79-1.508-.512-1.3-1.25-1.646-1.25-1.646-1.022-.699.078-.685.078-.685 1.13.08 1.724 1.16 1.724 1.16 1.004 1.72 2.635 1.223 3.277.936.102-.728.393-1.224.715-1.506-2.498-.284-5.124-1.25-5.124-5.563 0-1.23.44-2.234 1.16-3.022-.117-.284-.503-1.43.11-2.98 0 0 .945-.303 3.094 1.154A10.79 10.79 0 0 1 12 6.18a10.8 10.8 0 0 1 2.813.378c2.15-1.457 3.093-1.154 3.093-1.154.614 1.55.228 2.696.112 2.98.722.788 1.158 1.792 1.158 3.022 0 4.324-2.63 5.276-5.135 5.554.404.35.764 1.042.764 2.1 0 1.516-.014 2.738-.014 3.11 0 .3.203.65.774.54A11.25 11.25 0 0 0 12 .75Z" />
          </svg>
        </a>
        <a
          className="social-button"
          href="https://www.linkedin.com/in/martin-olarte-pallares/"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Martin Olarte on LinkedIn"
          title="LinkedIn"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
            <path d="M20.45 2H3.55C2.69 2 2 2.68 2 3.52v16.96c0 .84.69 1.52 1.55 1.52h16.9c.86 0 1.55-.68 1.55-1.52V3.52c0-.84-.69-1.52-1.55-1.52ZM7.93 18.75H4.98V9.2h2.95v9.55ZM6.46 7.9a1.71 1.71 0 1 1 0-3.42 1.71 1.71 0 0 1 0 3.42Zm12.29 10.85H15.8v-4.64c0-1.1-.02-2.52-1.54-2.52-1.54 0-1.78 1.2-1.78 2.44v4.72H9.53V9.2h2.83v1.3h.04c.39-.74 1.36-1.52 2.79-1.52 2.99 0 3.56 1.97 3.56 4.53v5.24Z" />
          </svg>
        </a>
      </nav>
    </header>
  )
}
