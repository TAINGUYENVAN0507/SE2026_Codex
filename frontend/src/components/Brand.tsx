import { WaveformIcon } from '@phosphor-icons/react/dist/csr/Waveform'
import { Link } from 'react-router-dom'

export function Brand() {
  return (
    <Link
      className="brand"
      to="/meetings"
      aria-label="Biên bản, về danh sách cuộc họp"
    >
      <span className="brand-mark">
        <WaveformIcon size={23} />
      </span>
      <span>Biên bản</span>
    </Link>
  )
}
