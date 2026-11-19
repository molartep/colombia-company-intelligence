import { formatNumber } from '../i18n/format'
import { errorMessage } from '../i18n/messages'
import { t, useLanguage } from '../i18n'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export function DirectoryImport({ onImported }: { onImported?: () => void } = {}) {
  useLanguage()

  const client = useQueryClient()
  const [token, setToken] = useState('')
  const [file, setFile] = useState<File>()
  const [fileError, setFileError] = useState('')
  const task = useMutation({
    mutationKey: ['rnve-import'],
    mutationFn: (selected?: File) => api.importDirectory(selected, token || undefined),
    onSuccess: async () => {
      setToken('')
      await Promise.all([
        client.invalidateQueries({ queryKey: ['platform'] }),
        client.invalidateQueries({ queryKey: ['capital-markets'] }),
        client.invalidateQueries({ queryKey: ['securities'] }),
        client.invalidateQueries({
          queryKey: ['search'],
          refetchType: onImported ? 'none' : 'active',
        }),
      ])
      onImported?.()
    },
  })
  return (
    <div className="directory-import">
      <p className="small">{t('common.importTheOfficialSfcIssuerOnlyExcelExportDownloadAnd')}</p>
      <button
        type="button"
        className="refresh-button"
        disabled={task.isPending}
        aria-busy={task.isPending}
        onClick={() => task.mutate(undefined)}
      >
        {task.isPending ? t('common.importingRnveDirectory') : t('common.importRnveDirectory')}
      </button>
      <details className="import-options">
        <summary>{t('common.importADownloadedXlsxAdministratorAccess')}</summary>
        <p className="small">
          {' '}
          {t('common.ifAutomaticDownloadFailsOpenThe')}{' '}
          <a
            className="text-link"
            href="https://www.superfinanciera.gov.co/SIMEV2/rnve/emisoresinscritosvigentes"
            target="_blank"
            rel="noreferrer"
          >
            {' '}
            {t('common.officialRnveDirectory')}
          </a>{' '}
          {t('common.andSelectDescargarEmisoresReporteExcelChooseThatIssuerOnly')}
        </p>
        <label>
          {' '}
          {t('common.officialIssuerXlsxMaximum10Mib')}{' '}
          <input
            type="file"
            accept=".xlsx"
            disabled={task.isPending}
            onChange={(event) => {
              const selected = event.target.files?.[0]
              setFileError('')
              if (
                selected &&
                (selected.size > 10 * 1024 * 1024 || !selected.name.toLowerCase().endsWith('.xlsx'))
              ) {
                setFile(undefined)
                setFileError('common.chooseAnXlsxFileNoLargerThan10Mib')
              } else setFile(selected)
            }}
          />
        </label>
        <label>
          {' '}
          {t('common.administratorImportKeyRequiredOnADeployedServer')}{' '}
          <input
            type="password"
            value={token}
            autoComplete="off"
            disabled={task.isPending}
            onChange={(event) => setToken(event.target.value)}
          />
        </label>
        <p className="small muted">{t('common.theKeyStaysInThisFormSMemoryAndIs')}</p>
        <button
          type="button"
          className="refresh-button"
          disabled={!file || task.isPending}
          onClick={() => task.mutate(file)}
        >
          {' '}
          {t('common.importSelectedXlsx')}
        </button>
      </details>
      {fileError && <p role="alert">{t(fileError)}</p>}
      {task.isError && <p role="alert">{errorMessage(task.error)}</p>}
      {task.isSuccess && (
        <p role="status">
          {' '}
          {t('common.imported')} {formatNumber(task.data.record_count)}{' '}
          {t('common.issuersIdentityLinksWereReconciledAndDependentViewsRefreshedCoverage')}
        </p>
      )}
    </div>
  )
}
