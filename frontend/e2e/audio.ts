// WAV PCM tổng hợp trong RAM; không commit audio hay dùng bản ghi thật.
export function syntheticWav() {
  const sampleRate = 16_000
  const seconds = 4
  const size = sampleRate * seconds * 2
  const buffer = Buffer.alloc(44 + size)
  buffer.write('RIFF', 0)
  buffer.writeUInt32LE(36 + size, 4)
  buffer.write('WAVEfmt ', 8)
  buffer.writeUInt32LE(16, 16)
  buffer.writeUInt16LE(1, 20)
  buffer.writeUInt16LE(1, 22)
  buffer.writeUInt32LE(sampleRate, 24)
  buffer.writeUInt32LE(sampleRate * 2, 28)
  buffer.writeUInt16LE(2, 32)
  buffer.writeUInt16LE(16, 34)
  buffer.write('data', 36)
  buffer.writeUInt32LE(size, 40)
  for (let i = 0; i < sampleRate * seconds; i++) {
    buffer.writeInt16LE(
      Math.round(Math.sin((2 * Math.PI * 440 * i) / sampleRate) * 3000),
      44 + i * 2,
    )
  }
  return { name: 'e2e-synthetic.wav', mimeType: 'audio/wav', buffer }
}
