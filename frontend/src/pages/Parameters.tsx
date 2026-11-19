import { formatNumber } from '../i18n/format'
import { uiMessage } from '../i18n/messages'
import { formatDate } from '../i18n/format'
import { t, useLanguage } from '../i18n'
import { useState } from 'react'
import type { FixedFilterKey } from '../api/filters'
import { Link } from 'react-router-dom'
import { Failure, Loading } from '../components/Feedback'
import { useParameters } from '../hooks/useParameters'

export function Parameters() {
  useLanguage()

  const parameters = useParameters()
  const [activeGroup, setActiveGroup] = useState<FixedFilterKey>('status')
  return (
    <section className="parameters-page">
      <h1>{t('parameters.parameters')}</h1>
      <p className="parameters-intro">
        {' '}
        {t('parameters.codesAndDescriptionsAvailableInTheAdvancedSearchFiltersSource')}
      </p>
      {parameters.isPending && <Loading />}
      {parameters.isError && (
        <Failure error={parameters.error} retry={() => void parameters.refetch()} />
      )}
      {parameters.data && (
        <>
          <section className="panel">
            <h2>{t('parameters.openFilters')}</h2>
            <p>
              <strong>{t('parameters.registradoBvc')}</strong>{' '}
              {t('parameters.booleanCheckboxSelectedMeansOnlyRegistrationsWithVerifiedIssuerLinks')}{' '}
              <strong>Acciones ordinarias</strong> {t('parameters.andMarket')} <strong>BVC</strong>{' '}
              {t('parameters.itFindsCandidateIssuersInTheRnveDirectoryRetrievesTheir')}
            </p>
            <p>{t('parameters.theSearchTableShowsAGreenCheckForEstablishedRegistration')}</p>
            <p>
              <strong>CIIU:</strong> {t('parameters.exactFourDigitCodeOrOneToFourDigitPrefix')}
            </p>
            <p>
              <strong>{t('parameters.dates')}</strong>{' '}
              {t('parameters.inclusiveRangesMissingMalformedImpossibleZeroAndYear9999Placeholders')}
            </p>
            <p>
              <strong>{t('parameters.renewedYear')}</strong>{' '}
              {t('parameters.exactlyTheSelectedYearOrThatYearAndLaterThis')}
            </p>
            <Link className="text-link" to="/">
              {' '}
              {t('parameters.returnToSearch')}
            </Link>
          </section>
          <div
            className="parameter-tabs"
            role="tablist"
            aria-label={t('parameters.parameterGroups')}
          >
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
                {uiMessage(group.title)} ({formatNumber(group.options.length)})
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
              <h2>{uiMessage(group.title)}</h2>
              <p>{uiMessage(group.description)}</p>
              <p className="small muted">
                {' '}
                {t('parameters.sourceFields')} <code>{group.code_field}</code> /{' '}
                <code>{group.label_field}</code>{' '}
                {t('parameters.theDescriptionIsTheReportedMeaningOfTheCodeNo')}
              </p>
              <div className="table-wrap">
                <table className="parameter-table">
                  <thead>
                    <tr>
                      <th scope="col">{t('parameters.code')}</th>
                      <th scope="col">{t('parameters.sourceDescriptionMeaning')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.options.map((option) => (
                      <tr key={option.value}>
                        <td>
                          <code>{option.code ?? t('parameters.missing')}</code>
                        </td>
                        <td>
                          {option.label ?? (
                            <span className="muted">
                              {' '}
                              {t('parameters.descriptionMissingFromSource')}
                            </span>
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
            <p>{uiMessage(parameters.data.note)}</p>
            <p>
              {' '}
              {t('parameters.verified')} {formatDate(parameters.data.verified_at, true)}
            </p>
            <p>
              {' '}
              {t('parameters.datasetUpdated')}{' '}
              {parameters.data.dataset_updated_at
                ? formatDate(parameters.data.dataset_updated_at, true)
                : t('parameters.notAvailable')}
            </p>
            <a
              className="text-link"
              href={parameters.data.source_url}
              target="_blank"
              rel="noreferrer"
            >
              {' '}
              {t('parameters.ruesConfecamarasSource')}
            </a>
          </div>
        </>
      )}
    </section>
  )
}
