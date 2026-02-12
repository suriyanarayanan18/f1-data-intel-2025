const DRIVER_ALIASES = {
  VER: 'max-verstappen',
  NOR: 'lando-norris',
  PIA: 'oscar-piastri',
  LEC: 'charles-leclerc',
  HAM: 'lewis-hamilton',
  RUS: 'george-russell',
  ALO: 'fernando-alonso',
  ALB: 'alex-albon',
  SAI: 'carlos-sainz',
  OCO: 'esteban-ocon',
  HUL: 'nico-hulkenberg',
  STR: 'lance-stroll',
}

const TEAM_ALIASES = {
  'Red Bull Racing': 'red-bull-racing',
  Ferrari: 'ferrari',
  McLaren: 'mclaren',
  Mercedes: 'mercedes',
  Williams: 'williams',
  'Aston Martin': 'aston-martin',
  'Haas F1 Team': 'haas',
  'Kick Sauber': 'kick-sauber',
  Alpine: 'alpine',
  'RB F1 Team': 'rb-f1-team',
}

function slugify(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function buildCandidates(folder, slug) {
  if (!slug) return []
  const root = `/media/${folder}/${slug}`
  return [`${root}.webp`, `${root}.png`, `${root}.jpg`, `${root}.jpeg`]
}

function normalizeDriver(value) {
  const raw = String(value || '').trim()
  const code = raw.toUpperCase()
  if (DRIVER_ALIASES[code]) return DRIVER_ALIASES[code]
  return slugify(raw)
}

function normalizeTeam(value) {
  const raw = String(value || '').trim()
  return TEAM_ALIASES[raw] || slugify(raw)
}

export function getDriverImage(driver) {
  return buildCandidates('drivers', normalizeDriver(driver))
}

export function getTeamLogo(team) {
  return buildCandidates('teams', normalizeTeam(team))
}

export function getCarImage(team) {
  return buildCandidates('cars', normalizeTeam(team))
}
