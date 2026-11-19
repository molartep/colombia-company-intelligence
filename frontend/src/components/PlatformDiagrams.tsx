import { t, useLanguage } from '../i18n'

function Arrow() {
  return (
    <svg
      className="flow-arrow"
      viewBox="0 0 32 32"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M4 16h23m-8-7 8 7-8 7" />
    </svg>
  )
}
function Node({ title, body }: { title: string; body: string }) {
  return (
    <div className="diagram-node">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  )
}
export function ArchitectureDiagram() {
  useLanguage()
  return (
    <figure className="platform-diagram" aria-label={t('advanced.diagrams.architectureLabel')}>
      <div className="architecture-trunk">
        <Node title="React + TypeScript" body={t('advanced.diagrams.browser')} />
        <div className="flow-down">
          <Arrow />
        </div>
        <Node title="FastAPI" body={t('advanced.diagrams.api')} />
        <div className="flow-down">
          <Arrow />
        </div>
      </div>
      <div className="architecture-branches">
        {['storage', 'rues', 'markets', 'secop'].map((key) => (
          <Node
            key={key}
            title={t(`advanced.diagrams.${key}Title`)}
            body={t(`advanced.diagrams.${key}Body`)}
          />
        ))}
      </div>
      <figcaption>{t('advanced.browsersCallThisApplicationSApiTheServerHandlesSource')}</figcaption>
    </figure>
  )
}
export function WorkflowDiagram() {
  useLanguage()
  return (
    <figure
      className="platform-diagram workflow-diagram"
      aria-label={t('advanced.diagrams.workflowLabel')}
    >
      <p className="workflow-entry">{t('advanced.diagrams.selectCompany')}</p>
      <div className="flow-down">
        <Arrow />
      </div>
      <div className="workflow-lanes">
        {['rues', 'markets', 'secop'].map((key) => (
          <div className="workflow-lane" key={key}>
            <h3>{t(`advanced.diagrams.${key}Title`)}</h3>
            <ol>
              {[1, 2, 3].map((step, index) => (
                <li key={step}>
                  {index > 0 && <Arrow />}
                  <span>{t(`advanced.diagrams.${key}Step${step}`)}</span>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
      <div className="flow-down">
        <Arrow />
      </div>
      <figcaption className="workflow-entry">{t('advanced.diagrams.result')}</figcaption>
    </figure>
  )
}
