import { useEffect, useRef, useState } from 'react'

export function SearchForm({
  initial = '',
  onSearch,
  disabled = false,
}: {
  initial?: string
  onSearch: (value: string) => void
  disabled?: boolean
}) {
  const [value, setValue] = useState(initial)
  const previous = useRef(initial)
  useEffect(() => {
    if (initial !== previous.current) {
      previous.current = initial
      // Synchronize browser back/forward navigation without remounting the focused input.
      setValue(initial)
    }
  }, [initial])
  return (
    <form
      className="search-form"
      onSubmit={(event) => {
        event.preventDefault()
        if (!disabled && value.trim().length >= 2) {
          previous.current = value.trim()
          onSearch(value.trim())
        }
      }}
    >
      <label htmlFor="company-search">Company name or NIT</label>
      <div className="search-control">
        <span aria-hidden="true">⌕</span>
        <input
          id="company-search"
          name="q"
          type="search"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Enter a legal name or NIT"
          minLength={2}
          maxLength={160}
          autoComplete="off"
          required
        />
        <button type="submit" disabled={disabled}>
          Search <span aria-hidden="true">↗</span>
        </button>
      </div>
    </form>
  )
}
