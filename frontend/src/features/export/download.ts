import type { ExportFormat } from '../../api/client'

export function exportFilename(
  disposition: string | null,
  format: ExportFormat,
) {
  const encoded = disposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const plain = disposition?.match(/filename="?([^";]+)"?/i)?.[1]
  let name = plain || ''
  try {
    if (encoded) name = decodeURIComponent(encoded)
  } catch {
    name = ''
  }
  name =
    name
      .split(/[\\/]/)
      .at(-1)
      ?.toLowerCase()
      .replace(/[^a-z0-9._-]/g, '-') || ''
  return /^[a-z0-9][a-z0-9._-]*$/.test(name) && name.endsWith(`.${format}`)
    ? name
    : `bien-ban.${format}`
}

export function saveExport(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
