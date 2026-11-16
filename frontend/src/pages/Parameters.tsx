import { useState } from 'react'
import type { FixedFilterKey } from '../api/filters'
import { Link } from 'react-router-dom'
import { Failure, Loading } from '../components/Feedback'
import { useParameters } from '../hooks/useParameters'

export function Parameters() {
  const parameters = useParameters()
  const [activeGroup, setActiveGroup] = useState<FixedFilterKey>('status')
  return (
    <section className="parameters-page">
      <h1>Parameters</h1>
      <p className="parameters-intro">
        Codes and descriptions available in the advanced search filters. Source labels are shown
        verbatim, including distinctions and missing descriptions.
      </p>
      {parameters.isPending && <Loading />}
      {parameters.isError && (
        <Failure error={parameters.error} retry={() => void parameters.refetch()} />
      )}
      {parameters.data && (
        <>
          <section className="panel">
            <h2>Open filters</h2>
            <p>
              <strong>Registrado BVC:</strong> boolean checkbox; selected means only registrations
              with verified issuer links and at least one retrieved RNVE record with category{' '}
              <strong>Acciones ordinarias</strong> and market <strong>BVC</strong>. It finds
              candidate issuers in the RNVE directory, retrieves their securities records using the
              existing cache, and restricts live RUES requests by eligible NIT before pagination.
              Existing table filters and pages do not limit discovery. Unchecked means no BVC
              restriction.
            </p>
            <p>
              The search table shows a green check for established registration evidence. A blank
              cell means registration has not been established, not that the company is
              unregistered. New companies do not need to have been searched or opened before.
              Coverage depends on the imported RNVE directory and successfully retrieved securities
              evidence; no current trading, price, liquidity or complete market coverage is implied.
            </p>
            <p>
              <strong>CIIU:</strong> exact four-digit code or one-to-four-digit prefix; primary
              activity or any of the four reported activities. No authoritative description lookup
              is integrated.
            </p>
            <p>
              <strong>Dates:</strong> inclusive ranges. Missing, malformed, impossible, zero and
              year-9999 placeholders are excluded when a range is used.
            </p>
            <p>
              <strong>Renewed year:</strong> exactly the selected year or that year and later. This
              uses the reported last renewed year independently of renewal dates.
            </p>
            <Link className="text-link" to="/">
              Return to Search →
            </Link>
          </section>
          <div className="parameter-tabs" role="tablist" aria-label="Parameter groups">
            {parameters.data.groups.map((group, index) => (
              <button
                key={group.key}
                type="button"
                role="tab"
                id={`parameter-tab-${group.key}`}
                aria-controls={`parameter-${group.key}`}
                aria-selected={activeGroup === group.key}
                tabIndex={activeGroup === group.key ? 0 : -1}
                onClick={() => setActiveGroup(group.key)}
                onKeyDown={(event) => {
                  const groups = parameters.data.groups
                  let next = index
                  if (event.key === 'ArrowRight') next = (index + 1) % groups.length
                  else if (event.key === 'ArrowLeft')
                    next = (index - 1 + groups.length) % groups.length
                  else if (event.key === 'Home') next = 0
                  else if (event.key === 'End') next = groups.length - 1
                  else return
                  event.preventDefault()
                  const group = groups[next]!
                  setActiveGroup(group.key)
                  const tabs =
                    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>(
                      '[role="tab"]',
                    )
                  tabs?.[next]?.focus()
                }}
              >
                {group.title} ({group.options.length})
              </button>
            ))}
          </div>
          {parameters.data.groups.map((group) => (
            <section
              className="parameter-section"
              id={`parameter-${group.key}`}
              key={group.key}
              role="tabpanel"
              aria-labelledby={`parameter-tab-${group.key}`}
              hidden={activeGroup !== group.key}
              tabIndex={0}
            >
              <h2>{group.title}</h2>
              <p>{group.description}</p>
              <p className="small muted">
                Source fields: <code>{group.code_field}</code> / <code>{group.label_field}</code>.
                The description is the reported meaning of the code; no additional legal
                interpretation is implied.
              </p>
              <div className="table-wrap">
                <table className="parameter-table">
                  <thead>
                    <tr>
                      <th scope="col">Code</th>
                      <th scope="col">Source description / meaning</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.options.map((option) => (
                      <tr key={option.value}>
                        <td>
                          <code>{option.code ?? 'Missing'}</code>
                        </td>
                        <td>
                          {option.label ?? (
                            <span className="muted">Description missing from source</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
          <div className="notice">
            <p>{parameters.data.note}</p>
            <p>Verified: {new Date(parameters.data.verified_at).toLocaleString()}</p>
            <p>
              Dataset updated:{' '}
              {parameters.data.dataset_updated_at
                ? new Date(parameters.data.dataset_updated_at).toLocaleString()
                : 'Not available'}
            </p>
            <a
              className="text-link"
              href={parameters.data.source_url}
              target="_blank"
              rel="noreferrer"
            >
              RUES / Confecámaras source ↗
            </a>
          </div>
        </>
      )}
    </section>
  )
}
