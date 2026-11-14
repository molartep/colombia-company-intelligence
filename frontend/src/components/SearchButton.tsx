export function SearchButton({ disabled = false }: { disabled?: boolean }) {
  return (
    <button className="search-submit" type="submit" disabled={disabled}>
      Search <span aria-hidden="true">↗</span>
    </button>
  )
}
