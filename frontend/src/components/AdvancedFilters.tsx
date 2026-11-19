import { formatNumber } from '../i18n/format'
import { uiMessage } from '../i18n/messages'
import { t, useLanguage } from '../i18n'
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
  useLanguage()

  const id = useId()
  return (
    <span className="filter-help">
      <button
        type="button"
        aria-label={t('filters.helpValue', { value0: label })}
        aria-describedby={id}
      >
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
  return `${option.code ?? t('filters.missingCode')} · ${option.label ?? t('filters.descriptionMissingFromSource')}`
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
  useLanguage()

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
        {' '}
        {t('filters.advancedFilters')}{' '}
        {count > 0 && (
          <span className="filter-count">
            {formatNumber(count)} {t('filters.selected')}
          </span>
        )}
      </summary>
      <div className="advanced-filters-body">
        <p className="filter-intro">
          <Link to="/parameters">{t('filters.viewParameters')}</Link>
        </p>
        <fieldset disabled={disabled}>
          <legend className="sr-only">{t('filters.advancedSearchFilters')}</legend>
          {parameters.isPending && (
            <p role="status">{t('filters.loadingAvailableFilterOptions')}</p>
          )}
          {parameters.isError && (
            <p role="alert">
              {' '}
              {t('filters.filterOptionsCouldNotBeLoaded')}{' '}
              <button type="button" onClick={() => void parameters.refetch()}>
                {' '}
                {t('filters.retry')}
              </button>
            </p>
          )}
          <div className="filter-grid">
            {parameters.data?.groups?.map((group) => (
              <div className="filter-field" key={group.key}>
                <div className="filter-label">
                  <span id={`label-${group.key}`}>{uiMessage(group.title)}</span>
                  <FilterHelp
                    label={uiMessage(group.title)}
                    text={t('filters.valueChooseAnyNumberNoSelectionMeansAllValues', {
                      value0: uiMessage(group.description),
                    })}
                  />
                </div>
                <details className="multi-select">
                  <summary aria-labelledby={`label-${group.key}`}>
                    {values[group.key].length
                      ? t('filters.valueSelected', { value0: values[group.key].length })
                      : t('filters.allValues')}
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
                      <span>{t('filters.selectAll')}</span>
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
                <label htmlFor="filter-ciiu">{t('filters.economicActivityCiiu')}</label>
                <FilterHelp
                  label={t('filters.economicActivityCiiu')}
                  text={t('filters.enterAnOfficialCodeKeepingLeadingZeroesExactRequiresFour')}
                />
              </div>
              <input
                id="filter-ciiu"
                inputMode="numeric"
                value={values.ciiu}
                maxLength={4}
                pattern={values.ciiu_match === 'exact' ? '[0-9]{4}' : '[0-9]{1,4}'}
                placeholder={t('filters.eG6201')}
                onChange={(event) => update('ciiu', event.target.value)}
              />
              <div className="filter-pair">
                <label>
                  {' '}
                  {t('filters.codeMatching')}{' '}
                  <select
                    value={values.ciiu_match}
                    onChange={(event) => update('ciiu_match', event.target.value)}
                  >
                    <option value="exact">{t('filters.exactCode')}</option>
                    <option value="prefix">{t('filters.codePrefix')}</option>
                  </select>
                </label>
                <label>
                  {' '}
                  {t('filters.activityScope')}{' '}
                  <select
                    value={values.ciiu_scope}
                    onChange={(event) => update('ciiu_scope', event.target.value)}
                  >
                    <option value="primary">{t('filters.primaryOnly')}</option>
                    <option value="any">{t('filters.anyReportedActivity')}</option>
                  </select>
                </label>
              </div>
            </div>
            <div className="filter-field">
              <div className="filter-label">
                <label htmlFor="filter-year">{t('filters.lastRenewedYear')}</label>
                <FilterHelp
                  label={t('filters.lastRenewedYear')}
                  text={t('filters.filterTheReportedLastRenewedYearNotTheRenewalDate')}
                />
              </div>
              <input
                id="filter-year"
                type="number"
                min="1000"
                max="9998"
                step="1"
                value={values.renewed_year}
                placeholder={t('filters.allYears')}
                onChange={(event) => update('renewed_year', event.target.value)}
              />
              <label>
                {' '}
                {t('filters.yearMatching')}{' '}
                <select
                  value={values.renewed_year_mode}
                  onChange={(event) => update('renewed_year_mode', event.target.value)}
                >
                  <option value="exact">{t('filters.exactlyThisYear')}</option>
                  <option value="minimum">{t('filters.thisYearOrLater')}</option>
                </select>
              </label>
            </div>
            {(['registration', 'renewal'] as const).map((kind) => (
              <div className="filter-field" key={kind}>
                <div className="filter-label">
                  <span>
                    {kind === 'registration'
                      ? t('filters.registrationDates')
                      : t('filters.renewalDates')}
                  </span>
                  <FilterHelp
                    label={t('filters.valueDates', { value0: kind })}
                    text={t('filters.inclusiveCalendarDateRangeBlankEndpointsAreUnrestrictedWhenA')}
                  />
                </div>
                <div className="filter-pair">
                  <label htmlFor={`${kind}-from`}>
                    {' '}
                    {t('filters.from')}{' '}
                    <input
                      id={`${kind}-from`}
                      aria-label={t('filters.valueDateFrom', {
                        value0:
                          kind === 'registration'
                            ? t('filters.registration')
                            : t('filters.renewal'),
                      })}
                      type="date"
                      min="0001-01-01"
                      max={values[`${kind}_to`] || '9998-12-31'}
                      value={values[`${kind}_from`]}
                      onChange={(event) => update(`${kind}_from`, event.target.value)}
                    />
                  </label>
                  <label htmlFor={`${kind}-to`}>
                    {' '}
                    {t('filters.to')}{' '}
                    <input
                      id={`${kind}-to`}
                      aria-label={t('filters.valueDateTo', {
                        value0:
                          kind === 'registration'
                            ? t('filters.registration')
                            : t('filters.renewal'),
                      })}
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
              {' '}
              {t('filters.clearFilters')}
            </button>
            <SearchButton disabled={disabled} />
          </div>
        </fieldset>
      </div>
    </details>
  )
}
