export function configureStorage(): string
export function createStorage(): { directory: string; cleanup(): void }
export function cleanupStorage(directory: string, token: string): void
export function cleanupAfterStack(): void
