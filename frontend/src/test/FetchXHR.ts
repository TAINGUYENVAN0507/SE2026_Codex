// Adapter test nối sự kiện XHR với fetch để MSW chạy trong Node/jsdom.
// Browser E2E vẫn dùng XMLHttpRequest thật; unit test upload kiểm multipart/progress.
export class FetchXHR {
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 0
  responseText = ''
  withCredentials = false
  private headers = new Headers()
  private responseHeaders = new Headers()
  private controller = new AbortController()
  private method = 'POST'
  private url = ''
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(name: string, value: string) {
    this.headers.set(name, value)
  }
  getResponseHeader(name: string) {
    return this.responseHeaders.get(name)
  }
  send(body: FormData) {
    void fetch(new URL(this.url, window.location.origin), {
      method: this.method,
      headers: this.headers,
      body,
      signal: this.controller.signal,
    })
      .then(async (response) => {
        this.status = response.status
        this.responseHeaders = response.headers
        this.responseText = await response.text()
        this.onload?.()
      })
      .catch(() => {
        if (!this.controller.signal.aborted) this.onerror?.()
      })
  }
  abort() {
    this.controller.abort()
    this.onabort?.()
  }
}
