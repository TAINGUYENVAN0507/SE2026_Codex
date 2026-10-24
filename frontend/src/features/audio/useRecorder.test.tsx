import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRecorder } from './useRecorder'

class FakeTrack {
  readyState: MediaStreamTrackState = 'live'
  stop = vi.fn(() => {
    this.readyState = 'ended'
  })
}

class FakeRecorder {
  static instances: FakeRecorder[] = []
  static isTypeSupported = vi.fn(
    (type: string) => type === 'audio/webm;codecs=opus',
  )
  state: RecordingState = 'inactive'
  mimeType: string
  ondataavailable: ((event: BlobEvent) => void) | null = null
  onstop: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(_source: MediaStream, options?: MediaRecorderOptions) {
    this.mimeType = options?.mimeType ?? ''
    FakeRecorder.instances.push(this)
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.onstop?.()
  }
  chunk() {
    this.ondataavailable?.({ data: new Blob(['audio']) } as BlobEvent)
  }
}

const originalMediaDevices = Object.getOwnPropertyDescriptor(
  navigator,
  'mediaDevices',
)
let tracks: FakeTrack[]
let getUserMedia: ReturnType<typeof vi.fn>

beforeEach(() => {
  tracks = [new FakeTrack(), new FakeTrack()]
  getUserMedia = vi.fn(
    async () => ({ getTracks: () => tracks }) as unknown as MediaStream,
  )
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  })
  vi.stubGlobal('MediaRecorder', FakeRecorder)
})

afterEach(() => {
  FakeRecorder.instances = []
  FakeRecorder.isTypeSupported.mockClear()
  vi.unstubAllGlobals()
  if (originalMediaDevices)
    Object.defineProperty(navigator, 'mediaDevices', originalMediaDevices)
  else Reflect.deleteProperty(navigator, 'mediaDevices')
})

describe('FE-06 useRecorder privacy and states', () => {
  it('PRIV-02: never requests the microphone before consent', async () => {
    const onRecorded = vi.fn()
    const { result } = renderHook(() => useRecorder(onRecorded))
    expect(result.current.status).toBe('idle')
    await act(async () => result.current.start(false))
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(result.current.status).toBe('idle')
    expect(onRecorded).not.toHaveBeenCalled()
  })

  it('PRIV-04: requests, records, stops all tracks and only prepares a local file', async () => {
    const onRecorded = vi.fn()
    const { result } = renderHook(() => useRecorder(onRecorded))
    let resolve!: (stream: MediaStream) => void
    getUserMedia.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    await act(async () => {
      void result.current.start(true)
    })
    expect(result.current.status).toBe('requesting')
    await act(async () =>
      resolve({ getTracks: () => tracks } as unknown as MediaStream),
    )
    await waitFor(() => expect(result.current.status).toBe('recording'))
    expect(FakeRecorder.instances[0].mimeType).toBe('audio/webm;codecs=opus')
    FakeRecorder.instances[0].chunk()
    act(() => result.current.stop())
    expect(result.current.status).toBe('stopped')
    expect(tracks.every((track) => track.readyState === 'ended')).toBe(true)
    expect(onRecorded).toHaveBeenCalledWith(
      expect.any(File),
      expect.any(Number),
    )
  })

  it('PRIV-05: cancel ends every track and does not upload or deliver a file', async () => {
    const onRecorded = vi.fn()
    const { result } = renderHook(() => useRecorder(onRecorded))
    await act(async () => result.current.start(true))
    expect(result.current.status).toBe('recording')
    act(() => result.current.cancel())
    expect(result.current.status).toBe('idle')
    expect(tracks.every((track) => track.readyState === 'ended')).toBe(true)
    expect(onRecorded).not.toHaveBeenCalled()
  })

  it('cancels a pending permission request before recording starts', async () => {
    let resolve!: (stream: MediaStream) => void
    getUserMedia.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
    const onRecorded = vi.fn()
    const { result } = renderHook(() => useRecorder(onRecorded))
    await act(async () => {
      void result.current.start(true)
    })
    act(() => result.current.cancel())
    await act(async () =>
      resolve({ getTracks: () => tracks } as unknown as MediaStream),
    )
    expect(result.current.status).toBe('idle')
    expect(tracks.every((track) => track.readyState === 'ended')).toBe(true)
    expect(FakeRecorder.instances).toHaveLength(0)
    expect(onRecorded).not.toHaveBeenCalled()
  })

  it('PRIV-09: unmount stops tracks even while recording', async () => {
    const { result, unmount } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => result.current.start(true))
    unmount()
    expect(tracks.every((track) => track.readyState === 'ended')).toBe(true)
  })

  it('uses the supported fallback MIME and reports denied permission', async () => {
    FakeRecorder.isTypeSupported.mockImplementation(
      (type) => type === 'audio/ogg;codecs=opus',
    )
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => result.current.start(true))
    expect(FakeRecorder.instances[0].mimeType).toBe('audio/ogg;codecs=opus')
    act(() => result.current.cancel())
    getUserMedia.mockRejectedValueOnce(new Error('denied'))
    await act(async () => result.current.start(true))
    expect(result.current.status).toBe('denied')
  })

  it('moves from stopped to uploading and done only on explicit actions', async () => {
    const { result } = renderHook(() => useRecorder(vi.fn()))
    await act(async () => result.current.start(true))
    act(() => result.current.stop())
    expect(result.current.status).toBe('stopped')
    act(() => result.current.startUpload())
    expect(result.current.status).toBe('uploading')
    act(() => result.current.finishUpload())
    expect(result.current.status).toBe('done')
  })
})
