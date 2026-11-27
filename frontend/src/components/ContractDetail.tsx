import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useCurrencyAmounts } from '../presentation/context'
import { t, useLanguage } from '../i18n'
import { formatDate } from '../i18n/format'
import { uiMessage } from '../i18n/messages'
import type { Contract } from '../types/secop'
import { Failure, Loading } from './Feedback'

const shown = (value: string | null | undefined) => value || t('governmentContracts.noInformado')
const sourceValue = (value: string | null | undefined) => shown(value).toLocaleUpperCase('es-CO')
const timestamp = (value: string | null) =>
  value ? formatDate(value, true) : t('governmentContracts.sinConsulta')

export function SourceLink({ contract }: { contract: Contract }) {
  useLanguage()

  return (
    <a className="text-link" href={contract.source_url} target="_blank" rel="noreferrer">
      {uiMessage(contract.source_link_label)} ↗
    </a>
  )
}
export function ContractDetail({
  companyId,
  id,
  runId,
  close,
}: {
  companyId: string
  id: string
  runId: string
  close: () => void
}) {
  useLanguage()
  const money = useCurrencyAmounts()

  const query = useQuery({
    queryKey: ['secop-detail', companyId, id, runId],
    queryFn: ({ signal }) => api.secopContract(companyId, id, signal, runId),
  })
  return (
    <section
      className="panel secop-detail"
      aria-label={t('governmentContracts.detalleDelContrato')}
    >
      <button className="refresh-button" onClick={close}>
        {' '}
        {t('governmentContracts.cerrarDetalle')}
      </button>
      <h3>
        {' '}
        {t('governmentContracts.detalleDelContrato')} {id}
      </h3>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <Failure error={query.error} retry={() => void query.refetch()} />
      ) : (
        <>
          <p>{shown(query.data.description)}</p>
          <dl>
            {Object.entries({
              [t('common.contract')]: query.data.contract_id,
              [t('common.process')]: query.data.process_id,
              [t('common.reference')]: query.data.reference,
              [t('governmentContracts.entidadContratante')]: sourceValue(query.data.buyer),
              [t('governmentContracts.nitDeLaEntidad')]: query.data.buyer_nit,
              [t('governmentContracts.documentoOriginalDelProveedor')]:
                query.data.original_supplier_identifier,
              [t('governmentContracts.nitNormalizadoDelProveedor')]:
                query.data.normalized_supplier_identifier,
              [t('governmentContracts.tipoDeDocumento')]: query.data.supplier_document_type,
              [t('common.match')]:
                `${t(`governmentContracts.matchMethods.${query.data.match_method}`, { defaultValue: query.data.match_method })} / ${t(`governmentContracts.matchStatuses.${query.data.match_status}`, { defaultValue: query.data.match_status })}`,
              [t('governmentContracts.valorReportado')]:
                query.data.value === null
                  ? null
                  : money.format(
                      query.data.value,
                      query.data.currency ?? t('governmentContracts.monedaNoInformada'),
                      false,
                      true,
                    ),
              [t('governmentContracts.estadoEnLaFuente')]: sourceValue(query.data.raw_status),
              [t('governmentContracts.tipoDeContrato')]: query.data.contract_type,
              [t('common.method')]: sourceValue(query.data.modality),
              [t('common.signature')]: formatDate(query.data.signature_date),
              [t('common.start')]: formatDate(query.data.start_date),
              [t('common.end')]: formatDate(query.data.end_date),
              [t('governmentContracts.departamentoDeLaEntidad')]: query.data.department,
              [t('governmentContracts.ciudadDeLaEntidad')]: query.data.city,
              [t('governmentContracts.filaDeLaFuente')]: query.data.source_identifier,
              [t('common.evidence')]: query.data.evidence_id,
              [t('common.retrieved')]: timestamp(query.data.retrieved_at),
              [t('governmentContracts.actualizacionDelContrato')]: timestamp(
                query.data.source_updated_at,
              ),
            }).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd
                  className={
                    key === t('governmentContracts.valorReportado') ? 'currency-value' : undefined
                  }
                >
                  {shown(value)}
                </dd>
              </div>
            ))}
          </dl>
          <SourceLink contract={query.data} />
        </>
      )}
    </section>
  )
}
