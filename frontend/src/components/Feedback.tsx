import { errorMessage } from '../i18n/messages'
import { t, useLanguage } from '../i18n'
import { useEffect, useRef } from 'react'
import { ApiError } from '../api/client'
import { DirectoryImport } from './DirectoryImport'

export function Failure({
  error,
  retry,
  message,
}: {
  error: Error
  retry?: () => void
  message?: string
}) {
  useLanguage()

  const needsImport = error instanceof ApiError && error.code === 'bvc_directory_unavailable'
  return (
    <div className="notice danger" role="alert">
      <strong>
        {needsImport
          ? t('feedback.theRnveIssuerDirectoryNeedsImporting')
          : t('feedback.weCouldnTRetrieveThisInformation')}
      </strong>
      <p>{message ?? errorMessage(error)}</p>
      {needsImport && <DirectoryImport onImported={retry} />}
      {retry && (
        <button className="text-link" onClick={retry}>
          {' '}
          {t('feedback.tryAgain')}
        </button>
      )}
    </div>
  )
}
export function Loading() {
  useLanguage()

  return (
    <div role="status" className="notice">
      <span className="pulse" /> {t('feedback.consultingOfficialRecords')}
    </div>
  )
}

export function SearchLoadingDialog() {
  useLanguage()

  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => element?.close()
  }, [])
  return (
    <dialog
      ref={dialog}
      className="search-loading-dialog"
      aria-labelledby="search-loading-title"
      aria-describedby="search-loading-description"
    >
      <img
        className="search-loading-animation"
        src="/retrieving-results.gif"
        alt=""
        width="72"
        height="72"
      />
      <span className="search-loading-static" aria-hidden="true">
        ⌕
      </span>
      <div role="status" aria-live="polite">
        <h2 id="search-loading-title">{t('feedback.retrievingResults')}</h2>
        <p id="search-loading-description">
          {' '}
          {t('feedback.searchingOfficialCompanyRecordsPleaseWait')}
        </p>
      </div>
      <button
        type="button"
        className="refresh-button search-loading-dismiss"
        onClick={() => dialog.current?.close()}
      >
        {t('feedback.continueBrowsing')}
      </button>
    </dialog>
  )
}

export function RefreshAlert({
  children,
  refresh,
  refreshing = false,
}: {
  children: React.ReactNode
  refresh: () => void
  refreshing?: boolean
}) {
  useLanguage()

  return (
    <div className="notice warning refresh-alert" role="status">
      <div>{children}</div>
      <button
        type="button"
        className="refresh-button"
        disabled={refreshing}
        aria-busy={refreshing}
        onClick={refresh}
      >
        {refreshing ? t('feedback.refreshing') : t('feedback.refreshData')}
      </button>
    </div>
  )
}
