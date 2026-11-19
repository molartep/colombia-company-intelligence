import { useLanguage } from '../i18n'
import type { ReactNode } from 'react'

export function SourceInformationCard({
  title,
  id,
  children,
}: {
  title: string
  id: string
  children: ReactNode
}) {
  useLanguage()

  return (
    <details className="panel data-source-information" id={id} tabIndex={-1}>
      <summary className="source-card-heading">
        <h2>{title}</h2>
      </summary>
      <div className="source-card-content">{children}</div>
    </details>
  )
}
