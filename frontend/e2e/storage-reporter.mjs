// FE-17: fallback sau teardown khi Windows không gửi SIGTERM cho stack.
import { cleanupAfterStack } from './storage.mjs'
export default class StorageReporter {
  onExit() {
    cleanupAfterStack()
  }
}
