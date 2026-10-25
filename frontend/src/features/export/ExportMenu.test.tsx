import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import { handlers } from '../../mocks/handlers'
import { ExportMenu } from './ExportMenu'
import * as download from './download'
import fixture from '../../../../contracts/fixtures/api/meeting_processing.json'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  vi.restoreAllMocks()
})
afterAll(() => server.close())

describe('FE-15 export menu', () => {
  it('disables export with a reason when the transcript is not ready', () => {
    render(<ExportMenu meetingId={fixture.id} ready={false} />)
    expect(screen.getByRole('button', { name: 'Xuất biên bản' })).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Xuất biên bản' }),
    ).toHaveAttribute('title', 'Transcript chưa sẵn sàng để xuất.')
  })

  it.each([
    ['Văn bản (.txt)', 'txt'],
    ['Dữ liệu (.json)', 'json'],
    ['Markdown (.md)', 'md'],
  ])(
    'requests the selected format %s and AI variant',
    async (label, format) => {
      const save = vi.spyOn(download, 'saveExport').mockImplementation(() => {})
      let requested = ''
      server.use(
        http.get('*/api/v1/meetings/:id/export', ({ request }) => {
          requested = request.url
          return new HttpResponse('fixture file', {
            headers: {
              'Content-Disposition': `attachment; filename*=UTF-8''hop-2026-10-25.${format}`,
            },
          })
        }),
      )
      const user = userEvent.setup()
      render(<ExportMenu meetingId={fixture.id} ready />)
      await user.click(screen.getByRole('button', { name: 'Xuất biên bản' }))
      await user.selectOptions(
        screen.getByRole('combobox', { name: 'Phiên bản xuất' }),
        'ai_original',
      )
      await user.click(screen.getByRole('button', { name: label }))
      await waitFor(() => expect(save).toHaveBeenCalled())
      const url = new URL(requested)
      expect(url.pathname).toBe(`/api/v1/meetings/${fixture.id}/export`)
      expect(url.searchParams.get('format')).toBe(format)
      expect(url.searchParams.get('variant')).toBe('ai_original')
      expect(save).toHaveBeenCalledWith(
        expect.any(Blob),
        `hop-2026-10-25.${format}`,
      )
    },
  )

  it('downloads the current default variant through the shared MSW handler', async () => {
    const save = vi.spyOn(download, 'saveExport').mockImplementation(() => {})
    render(<ExportMenu meetingId={fixture.id} ready />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Xuất biên bản' }))
    await user.click(screen.getByRole('button', { name: 'Dữ liệu (.json)' }))
    await waitFor(() => expect(save).toHaveBeenCalled())
    const blob = save.mock.calls[0][0]
    expect(JSON.parse(await blob.text())).toMatchObject({
      schema_version: '1.0',
      variant: 'current',
    })
  })

  it('shows a toast for 409 and does not download', async () => {
    const save = vi.spyOn(download, 'saveExport').mockImplementation(() => {})
    server.use(
      http.get('*/api/v1/meetings/:id/export', () =>
        HttpResponse.json(
          { error: { code: 'TRANSCRIPT_NOT_READY', message: 'Not ready' } },
          { status: 409 },
        ),
      ),
    )
    render(<ExportMenu meetingId={fixture.id} ready />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Xuất biên bản' }))
    await user.click(screen.getByRole('button', { name: 'Văn bản (.txt)' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Transcript chưa sẵn sàng',
    )
    expect(save).not.toHaveBeenCalled()
  })

  it('uses a safe filename when Content-Disposition is malformed', () => {
    expect(
      download.exportFilename("attachment; filename*=UTF-8''%E0%A4%A", 'txt'),
    ).toBe('bien-ban.txt')
    expect(
      download.exportFilename('attachment; filename="../../tool.exe"', 'txt'),
    ).toBe('bien-ban.txt')
  })
})
