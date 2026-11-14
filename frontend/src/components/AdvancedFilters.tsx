import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  emptyFilters,
  fixedFilterKeys,
  type FilterValues,
  type ScalarFilterKey,
} from '../api/filters'
import { useParameters } from '../hooks/useParameters'
import type { ParameterOption } from '../types'
import { SearchButton } from './SearchButton'

export function FilterHelp({ text, label }: { text: string; label: string }) {
  const id = useId()
  return (
    <span className="filter-help">
      <button type="button" aria-label={`Help: ${label}`} aria-describedby={id}>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M12 11v5" strokeLinecap="round" />
          <circle cx="12" cy="7.5" r="1" fill="currentColor" stroke="none" />
        </svg>
      </button>
      <span id={id} role="tooltip">
        {text}
      </span>
    </span>
  )
}
function optionLabel(option: ParameterOption) {
  return `${option.code ?? 'Missing code'} · ${option.label ?? 'Description missing from source'}`
}
export function AdvancedFilters({
  values,
  onChange,
  disabled,
}: {
  values: FilterValues
  onChange: (values: FilterValues) => void
  disabled: boolean
}) {
  const [open, setOpen] = useState(false)
  const parameters = useParameters(open)
  const count =
    fixedFilterKeys.reduce((sum, key) => sum + values[key].length, 0) +
    [
      'ciiu',
      'registration_from',
      'registration_to',
      'renewal_from',
      'renewal_to',
      'renewed_year',
    ].filter((key) => values[key as ScalarFilterKey]).length
  const update = (key: ScalarFilterKey, value: string) => onChange({ ...values, [key]: value })
  return (
    <details className="advanced-filters" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>
        Advanced filters {count > 0 && <span className="filter-count">{count} selected</span>}
      </summary>
      <div className="advanced-filters-body">
        <p className="filter-intro">
          <Link to="/parameters">View parameters ↗</Link>
        </p>
        <fieldset disabled={disabled}>
          <legend className="sr-only">Advanced search filters</legend>
          {parameters.isPending && <p role="status">Loading available filter options…</p>}
          {parameters.isError && (
            <p role="alert">
              Filter options could not be loaded.{' '}
              <button type="button" onClick={() => void parameters.refetch()}>
                Retry
              </button>
            </p>
          )}
          <div className="filter-grid">
            {parameters.data?.groups?.map((group) => (
              <div className="filter-field" key={group.key}>
                <div className="filter-label">
                  <span id={`label-${group.key}`}>{group.title}</span>
                  <FilterHelp
                    label={group.title}
                    text={`${group.description} Choose any number; no selection means all values.`}
                  />
                </div>
                <details className="multi-select">
                  <summary aria-labelledby={`label-${group.key}`}>
                    {values[group.key].length
                      ? `${values[group.key].length} selected`
                      : 'All values'}
                  </summary>
                  <div
                    className="multi-select-options"
                    role="group"
                    aria-labelledby={`label-${group.key}`}
                  >
                    <label className="multi-select-all">
                      <input
                        type="checkbox"
                        checked={
                          group.options.length > 0 &&
                          group.options.every((option) => values[group.key].includes(option.value))
                        }
                        ref={(input) => {
                          if (input)
                            input.indeterminate =
                              group.options.some((option) =>
                                values[group.key].includes(option.value),
                              ) &&
                              !group.options.every((option) =>
                                values[group.key].includes(option.value),
                              )
                        }}
                        onChange={(event) =>
                          onChange({
                            ...values,
                            [group.key]: event.target.checked
                              ? group.options.map((option) => option.value)
                              : [],
                          })
                        }
                      />
                      <span>Select all</span>
                    </label>
                    {group.options.map((option) => (
                      <label key={option.value}>
                        <input
                          type="checkbox"
                          name={group.key}
                          value={option.value}
                          checked={values[group.key].includes(option.value)}
                          onChange={(event) =>
                            onChange({
                              ...values,
                              [group.key]: event.target.checked
                                ? [...values[group.key], option.value]
                                : values[group.key].filter((value) => value !== option.value),
                            })
                          }
                        />
                        <span>{optionLabel(option)}</span>
                      </label>
                    ))}
                  </div>
                </details>
              </div>
            ))}
            <div className="filter-field">
              <div className="filter-label">
                <label htmlFor="filter-ciiu">Economic activity / CIIU</label>
                <FilterHelp
                  label="Economic activity / CIIU"
                  text="Enter an official code, keeping leading zeroes. Exact requires four digits; prefix accepts one to four. Any activity checks primary, secondary, third and fourth codes. Descriptions have not been verified."
                />
              </div>
              <input
                id="filter-ciiu"
                inputMode="numeric"
                value={values.ciiu}
                maxLength={4}
                pattern={values.ciiu_match === 'exact' ? '[0-9]{4}' : '[0-9]{1,4}'}
                placeholder="e.g. 6201"
                onChange={(event) => update('ciiu', event.target.value)}
              />
              <div className="filter-pair">
                <label>
                  Code matching
                  <select
                    value={values.ciiu_match}
                    onChange={(event) => update('ciiu_match', event.target.value)}
                  >
                    <option value="exact">Exact code</option>
                    <option value="prefix">Code prefix</option>
                  </select>
                </label>
                <label>
                  Activity scope
                  <select
                    value={values.ciiu_scope}
                    onChange={(event) => update('ciiu_scope', event.target.value)}
                  >
                    <option value="primary">Primary only</option>
                    <option value="any">Any reported activity</option>
                  </select>
                </label>
              </div>
            </div>
            <div className="filter-field">
              <div className="filter-label">
                <label htmlFor="filter-year">Last renewed year</label>
                <FilterHelp
                  label="Last renewed year"
                  text="Filter the reported last renewed year, not the renewal date. Blank means all years; malformed and placeholder years are excluded when this filter is applied."
                />
              </div>
              <input
                id="filter-year"
                type="number"
                min="1000"
                max="9998"
                step="1"
                value={values.renewed_year}
                placeholder="All years"
                onChange={(event) => update('renewed_year', event.target.value)}
              />
              <label>
                Year matching
                <select
                  value={values.renewed_year_mode}
                  onChange={(event) => update('renewed_year_mode', event.target.value)}
                >
                  <option value="exact">Exactly this year</option>
                  <option value="minimum">This year or later</option>
                </select>
              </label>
            </div>
            {(['registration', 'renewal'] as const).map((kind) => (
              <div className="filter-field" key={kind}>
                <div className="filter-label">
                  <span>{kind === 'registration' ? 'Registration dates' : 'Renewal dates'}</span>
                  <FilterHelp
                    label={`${kind} dates`}
                    text="Inclusive calendar-date range. Blank endpoints are unrestricted. When a range is used, missing, malformed, impossible, zero and year-9999 placeholder dates are excluded rather than interpreted as events."
                  />
                </div>
                <div className="filter-pair">
                  <label htmlFor={`${kind}-from`}>
                    From
                    <input
                      id={`${kind}-from`}
                      aria-label={`${kind === 'registration' ? 'Registration' : 'Renewal'} date from`}
                      type="date"
                      min="0001-01-01"
                      max={values[`${kind}_to`] || '9998-12-31'}
                      value={values[`${kind}_from`]}
                      onChange={(event) => update(`${kind}_from`, event.target.value)}
                    />
                  </label>
                  <label htmlFor={`${kind}-to`}>
                    To
                    <input
                      id={`${kind}-to`}
                      aria-label={`${kind === 'registration' ? 'Registration' : 'Renewal'} date to`}
                      type="date"
                      min={values[`${kind}_from`] || '0001-01-01'}
                      max="9998-12-31"
                      value={values[`${kind}_to`]}
                      onChange={(event) => update(`${kind}_to`, event.target.value)}
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
          <div className="filter-footer">
            <button
              className="filter-clear"
              type="button"
              onClick={() => onChange({ ...emptyFilters })}
            >
              Clear filters
            </button>
            <SearchButton disabled={disabled} />
          </div>
        </fieldset>
      </div>
    </details>
  )
}
