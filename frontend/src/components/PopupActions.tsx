import { t, useLanguage } from '../i18n'
import { Tooltip } from './Tooltip'

/** Standard popup actions: optional standalone view, then Close at the far right. */
export function PopupActions({ close, href }: { close: () => void; href?: string }) {
  useLanguage()
  return (
    <div className="popup-actions">
      {href && (
        <Tooltip text={t('involvement.newTab')} className="popup-action-tooltip">
          {(id) => (
            <a
              className="popup-icon-action"
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t('involvement.newTab')}
              aria-describedby={id}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M14 3h7v7M21 3 11 13M10 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" />
              </svg>
            </a>
          )}
        </Tooltip>
      )}
      <Tooltip text={t('involvement.close')} className="popup-action-tooltip">
        {(id) => (
          <button
            type="button"
            className="popup-icon-action"
            onClick={close}
            aria-label={t('involvement.close')}
            aria-describedby={id}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <path d="m6 6 12 12M18 6 6 18" />
            </svg>
          </button>
        )}
      </Tooltip>
    </div>
  )
}
