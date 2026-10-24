const networkEvents = new EventTarget()

export function notifyNetworkFailure() {
  networkEvents.dispatchEvent(new Event('failure'))
}

export function onNetworkFailure(listener: () => void) {
  networkEvents.addEventListener('failure', listener)
  return () => networkEvents.removeEventListener('failure', listener)
}
