import { useEffect, useRef } from 'react'

export function Failure({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <div className="notice danger" role="alert">
      <strong>We couldn’t retrieve this information.</strong>
      <p>{error.message}</p>
      {retry && (
        <button className="text-link" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  )
}
export function Loading() {
  return (
    <div role="status" className="notice">
      <span className="pulse" /> Consulting official records…
    </div>
  )
}

export function SearchLoadingDialog() {
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
      onCancel={(event) => event.preventDefault()}
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
        <h2 id="search-loading-title">Retrieving results</h2>
        <p id="search-loading-description">Searching official company records. Please wait…</p>
      </div>
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
        {refreshing ? 'Refreshing…' : 'Refresh data'}
      </button>
    </div>
  )
}
