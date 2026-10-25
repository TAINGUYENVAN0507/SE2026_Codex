import { useEffect, useRef, useState } from 'react'
import { DownloadSimpleIcon } from '@phosphor-icons/react/dist/csr/DownloadSimple'
import { CaretDownIcon } from '@phosphor-icons/react/dist/csr/CaretDown'
import {
  getMeetingExport,
  type ExportFormat,
  type ExportVariant,
} from '../../api/client'
import { ApiError } from '../../api/errors'
import { exportFilename, saveExport } from './download'

export function ExportMenu({
  meetingId,
  ready,
}: {
  meetingId: string
  ready: boolean
}) {
  const [open, setOpen] = useState(false)
  const [variant, setVariant] = useState<ExportVariant>('current')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        trigger.current?.focus()
      }
    }
    document.addEventListener('pointerdown', outside)
    if (open) document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  async function download(format: ExportFormat) {
    if (!ready || busy) return
    setBusy(true)
    setError('')
    try {
      const result = await getMeetingExport(meetingId, format, variant)
      saveExport(result.blob, exportFilename(result.disposition, format))
      setOpen(false)
      trigger.current?.focus()
    } catch (cause) {
      setError(
        cause instanceof ApiError &&
          (cause.status === 409 || cause.code === 'TRANSCRIPT_NOT_READY')
          ? 'Transcript chưa sẵn sàng. Hãy chờ xử lý xong rồi thử xuất lại.'
          : 'Không thể xuất biên bản. Hãy thử lại.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="dropdown" ref={root}>
      <span title={!ready ? 'Transcript chưa sẵn sàng để xuất.' : undefined}>
        <button
          ref={trigger}
          className="button primary"
          aria-expanded={open}
          aria-controls="export-menu"
          disabled={!ready || busy}
          title={
            !ready
              ? 'Transcript chưa sẵn sàng để xuất.'
              : 'Xuất dữ liệu đã lưu trên máy chủ'
          }
          onClick={() => setOpen((value) => !value)}
        >
          <DownloadSimpleIcon />
          {busy ? 'Đang tải file…' : 'Xuất biên bản'}
          <CaretDownIcon size={12} />
        </button>
      </span>
      {open && (
        <div
          className="export-menu"
          id="export-menu"
          aria-label="Tùy chọn xuất biên bản"
        >
          <label>
            Phiên bản
            <select
              aria-label="Phiên bản xuất"
              value={variant}
              disabled={busy}
              onChange={(event) =>
                setVariant(event.target.value as ExportVariant)
              }
            >
              <option value="current">Bản hiện tại</option>
              <option value="ai_original">Bản AI gốc</option>
            </select>
          </label>
          {(['txt', 'json', 'md'] as const).map((format) => (
            <button
              key={format}
              disabled={busy}
              onClick={() => void download(format)}
            >
              {
                {
                  txt: 'Văn bản (.txt)',
                  json: 'Dữ liệu (.json)',
                  md: 'Markdown (.md)',
                }[format]
              }
            </button>
          ))}
        </div>
      )}
      {error && (
        <div className="network-toast" role="alert">
          <span>{error}</span>
          <button className="button quiet small" onClick={() => setError('')}>
            Đóng
          </button>
        </div>
      )}
    </div>
  )
}
