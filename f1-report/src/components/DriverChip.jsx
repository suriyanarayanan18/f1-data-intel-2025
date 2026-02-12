import { useMemo, useState } from 'react'
import { DRIVER_ASSETS } from '../data/driverAssets'

function initialsFromName(name, fallback) {
  if (!name) return fallback
  const parts = name.split(' ').filter(Boolean)
  if (!parts.length) return fallback
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] || ''}${parts[parts.length - 1][0] || ''}`.toUpperCase()
}

function DriverChip({ code, showName = true, className = '' }) {
  const [imageFailed, setImageFailed] = useState(false)
  const driver = DRIVER_ASSETS[code]

  const chipName = driver?.name || code
  const teamColor = driver?.teamColor || '#374151'
  const initials = useMemo(() => initialsFromName(chipName, code), [chipName, code])
  const hasImage = Boolean(driver?.image) && !imageFailed

  return (
    <div className={`driver-chip ${className}`.trim()} title={chipName}>
      <span className="driver-chip-avatar" style={{ backgroundColor: teamColor }}>
        {hasImage ? (
          <img src={driver.image} alt={chipName} onError={() => setImageFailed(true)} />
        ) : (
          <span className="driver-chip-fallback">{initials}</span>
        )}
      </span>
      {showName ? (
        <span className="driver-chip-text">
          <strong>{code}</strong>
          <small>{driver?.team || 'Unknown Team'}</small>
        </span>
      ) : null}
    </div>
  )
}

export default DriverChip
