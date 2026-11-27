import { useId, useState, type ReactNode } from 'react'

/** Shared hover/focus tooltip; its trigger supplies the accessible description. */
export function Tooltip({
  text,
  className = '',
  children,
}: {
  text: string
  className?: string
  children: (descriptionId: string) => ReactNode
}) {
  const id = useId()
  const [dismissed, setDismissed] = useState(false)
  return (
    <span
      className={`filter-help ${className}`.trim()}
      data-dismissed={dismissed || undefined}
      onMouseEnter={() => setDismissed(false)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setDismissed(false)
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') setDismissed(true)
      }}
    >
      {children(id)}
      <span id={id} role="tooltip">
        {text}
      </span>
    </span>
  )
}
