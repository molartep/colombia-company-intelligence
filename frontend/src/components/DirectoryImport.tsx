import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export function DirectoryImport({ onImported }: { onImported?: () => void } = {}) {
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
      <p className="small">
        Import the official SFC issuer-only Excel export. Download and validation can take up to 90
        seconds. Existing evidence is retained if validation fails.
      </p>
      <button
        type="button"
        className="refresh-button"
        disabled={task.isPending}
        aria-busy={task.isPending}
        onClick={() => task.mutate(undefined)}
      >
        {task.isPending ? 'Importing RNVE directory…' : 'Import RNVE directory'}
      </button>
      <details className="import-options">
        <summary>Import a downloaded XLSX / administrator access</summary>
        <p className="small">
          If automatic download fails, open the{' '}
          <a
            className="text-link"
            href="https://www.superfinanciera.gov.co/SIMEV2/rnve/emisoresinscritosvigentes"
            target="_blank"
            rel="noreferrer"
          >
            official RNVE directory ↗
          </a>{' '}
          and select DESCARGAR EMISORES → REPORTE EXCEL. Choose that issuer-only file below.
        </p>
        <label>
          Official issuer XLSX (maximum 10 MiB)
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
                setFileError('Choose an XLSX file no larger than 10 MiB.')
              } else setFile(selected)
            }}
          />
        </label>
        <label>
          Administrator import key (required on a deployed server)
          <input
            type="password"
            value={token}
            autoComplete="off"
            disabled={task.isPending}
            onChange={(event) => setToken(event.target.value)}
          />
        </label>
        <p className="small muted">
          The key stays in this form’s memory and is cleared after import. Local loopback use does
          not require a key.
        </p>
        <button
          type="button"
          className="refresh-button"
          disabled={!file || task.isPending}
          onClick={() => task.mutate(file)}
        >
          Import selected XLSX
        </button>
      </details>
      {fileError && <p role="alert">{fileError}</p>}
      {task.isError && <p role="alert">{task.error.message}</p>}
      {task.isSuccess && (
        <p role="status">
          Imported {task.data.record_count} issuers. Identity links were reconciled and dependent
          views refreshed. Coverage remains incomplete unless separately attested by an operator.
        </p>
      )}
    </div>
  )
}
