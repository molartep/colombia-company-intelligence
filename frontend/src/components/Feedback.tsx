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
