import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getCarImage, getDriverImage, getTeamLogo } from './media'
import './App.css'

const CHAPTERS = [
  { id: 'intro', navLabel: '00 Intro', title: 'F1 Data Intelligence Report 2025', kicker: 'Editorial' },
  { id: 'chapter-1', navLabel: '01 Season', title: 'Standings Momentum', kicker: 'Chapter 1' },
  { id: 'chapter-2', navLabel: '02 Qualifying', title: 'Qualifying Edge', kicker: 'Chapter 2' },
  { id: 'chapter-3', navLabel: '03 Pace', title: 'Race Pace Reality', kicker: 'Chapter 3' },
  { id: 'chapter-4', navLabel: '04 Pits', title: 'Pit Stop Intelligence', kicker: 'Chapter 4' },
  { id: 'chapter-5', navLabel: '05 Overtakes', title: 'The Overtake Report', kicker: 'Chapter 5' },
]

const SERIES_COLORS = ['#ff5500', '#ff7a2f', '#ff9c55', '#fdbf84', '#8ad0ff', '#4cb0ff', '#9af0cf', '#f8d26f']

function compactEventName(name) {
  return String(name || '').replace(' Grand Prix', '').replace('Emilia Romagna', 'Imola')
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function scale(value, fromMin, fromMax, toMin, toMax) {
  if (!Number.isFinite(value) || fromMax <= fromMin) return toMin
  const ratio = (value - fromMin) / (fromMax - fromMin)
  return toMin + ratio * (toMax - toMin)
}

function useJsonDataset(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let mounted = true
    async function load() {
      setLoading(true)
      setError('')
      try {
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Could not load ${url}.`)
        const payload = await response.json()
        if (mounted) setData(payload)
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : `Failed loading ${url}.`)
          setData(null)
        }
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [url])
  return { data, loading, error }
}

function ChapterStatus({ loading, error, missingText }) {
  if (loading) return <div className='status-card'>Loading chapter data...</div>
  if (error) return <div className='status-card status-error'>{error}</div>
  if (missingText) return <div className='status-card status-error'>{missingText}</div>
  return null
}

function MediaTile({ candidates, label, sublabel }) {
  const [resolvedSrc, setResolvedSrc] = useState('')
  const [isResolving, setIsResolving] = useState(true)
  const candidateKey = Array.isArray(candidates) ? candidates.join('|') : ''

  useEffect(() => {
    let cancelled = false
    setResolvedSrc('')
    setIsResolving(true)

    async function resolveImage() {
      if (!Array.isArray(candidates) || !candidates.length) {
        if (!cancelled) {
          setIsResolving(false)
        }
        return
      }

      for (const src of candidates) {
        const ok = await new Promise((resolve) => {
          const img = new Image()
          img.onload = () => resolve(true)
          img.onerror = () => resolve(false)
          img.src = src
        })
        if (ok) {
          if (!cancelled) {
            setResolvedSrc(src)
            setIsResolving(false)
          }
          return
        }
      }

      if (!cancelled) {
        setIsResolving(false)
      }
    }

    resolveImage()
    return () => {
      cancelled = true
    }
  }, [candidateKey])

  if (isResolving) {
    return <div className='media-fallback' aria-hidden='true' />
  }

  if (!resolvedSrc) {
    return <div className='media-fallback'><strong>{label}</strong>{sublabel ? <span>{sublabel}</span> : null}</div>
  }
  return <img src={resolvedSrc} alt={label} className='media-image' loading='eager' decoding='async' />
}


function App() {
  const navRef = useRef(null)
  const [activeSection, setActiveSection] = useState('intro')
  const [scrollProgress, setScrollProgress] = useState(0)
  const [spotlightMode, setSpotlightMode] = useState(true)
  const [showMethodology, setShowMethodology] = useState(false)

  const standings = useJsonDataset('/data/standings_progression.json')
  const heatmap = useJsonDataset('/data/points_heatmap.json')
  const q3 = useJsonDataset('/data/q3_gaps.json')
  const poleToWin = useJsonDataset('/data/pole_to_win.json')
  const pace = useJsonDataset('/data/ch3_pace.json')
  const pits = useJsonDataset('/data/ch4_pitstops.json')
  const overtakes = useJsonDataset('/data/ch5_overtakes.json')

  const [selectedQ3Round, setSelectedQ3Round] = useState(null)
  const [selectedPaceRound, setSelectedPaceRound] = useState(null)
  const [paceMetric, setPaceMetric] = useState('pace_delta_to_best_avg_s')
  const [selectedPitRound, setSelectedPitRound] = useState(null)
  const [pitMetric, setPitMetric] = useState('avg_pit_s')
  const [selectedOvertakeRound, setSelectedOvertakeRound] = useState(null)

  const chapterOrder = useMemo(() => CHAPTERS.map((entry) => entry.id), [])

  useEffect(() => {
    function syncScrollState() {
      const navHeight = navRef.current?.getBoundingClientRect().height ?? 0
      const marker = window.scrollY + navHeight + window.innerHeight * 0.36
      let current = chapterOrder[0]
      chapterOrder.forEach((id) => {
        const el = document.getElementById(id)
        if (el && el.offsetTop <= marker) current = id
      })
      setActiveSection(current)
      const scrollable = document.documentElement.scrollHeight - window.innerHeight
      const progress = scrollable > 0 ? window.scrollY / scrollable : 0
      setScrollProgress(clamp(progress, 0, 1))
    }

    syncScrollState()
    window.addEventListener('scroll', syncScrollState, { passive: true })
    window.addEventListener('resize', syncScrollState)
    return () => {
      window.removeEventListener('scroll', syncScrollState)
      window.removeEventListener('resize', syncScrollState)
    }
  }, [chapterOrder])

  function scrollToSection(id) {
    const target = document.getElementById(id)
    if (!target) return
    const navHeight = navRef.current?.getBoundingClientRect().height ?? 0
    const y = window.scrollY + target.getBoundingClientRect().top - navHeight - 10
    window.scrollTo({ top: y, behavior: 'smooth' })
  }

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      const target = event.target
      if (target instanceof HTMLElement) {
        const tag = target.tagName.toLowerCase()
        if (tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable) return
      }
      const idx = chapterOrder.findIndex((id) => id === activeSection)
      if (idx === -1) return
      if (event.key === 'ArrowRight' && idx < chapterOrder.length - 1) {
        event.preventDefault()
        scrollToSection(chapterOrder[idx + 1])
      }
      if (event.key === 'ArrowLeft' && idx > 0) {
        event.preventDefault()
        scrollToSection(chapterOrder[idx - 1])
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [activeSection, chapterOrder])

  const standingsRounds = useMemo(() => (Array.isArray(standings.data?.rounds) ? standings.data.rounds : []), [standings.data])
  const standingsRows = useMemo(() => (Array.isArray(standings.data?.rows) ? standings.data.rows : []), [standings.data])
  const topDrivers = useMemo(() => {
    if (!standingsRounds.length || !standingsRows.length) return []
    const finalRoundKey = String(standingsRounds[standingsRounds.length - 1].RoundNumber)
    return [...standingsRows]
      .map((row) => ({ driver: String(row.Driver || ''), points: Number(row[finalRoundKey] || 0), row }))
      .sort((a, b) => b.points - a.points)
      .slice(0, 6)
  }, [standingsRounds, standingsRows])
  const lineData = useMemo(() => {
    if (!standingsRounds.length || !topDrivers.length) return []
    return standingsRounds.map((round) => {
      const roundKey = String(round.RoundNumber)
      const record = { round: Number(round.RoundNumber), event: compactEventName(round.EventName) }
      topDrivers.forEach((driver) => {
        record[driver.driver] = Number(driver.row[roundKey] || 0)
      })
      return record
    })
  }, [standingsRounds, topDrivers])

  const heatmapRounds = useMemo(() => (Array.isArray(heatmap.data?.rounds) ? heatmap.data.rounds : []), [heatmap.data])
  const heatmapRows = useMemo(() => (Array.isArray(heatmap.data?.rows) ? heatmap.data.rows : []), [heatmap.data])
  const miniHeatmapRows = useMemo(() => {
    if (!heatmapRows.length || !heatmapRounds.length || !topDrivers.length) return []
    const topSet = new Set(topDrivers.map((row) => row.driver))
    return heatmapRows.filter((row) => topSet.has(String(row.Driver || '')))
  }, [heatmapRows, heatmapRounds, topDrivers])
  const heatMax = useMemo(() => {
    if (!miniHeatmapRows.length || !heatmapRounds.length) return 0
    return miniHeatmapRows.reduce((maxVal, row) => {
      return heatmapRounds.reduce((acc, round) => {
        const value = Number(row[String(round.RoundNumber)] || 0)
        return value > acc ? value : acc
      }, maxVal)
    }, 0)
  }, [miniHeatmapRows, heatmapRounds])

  const q3Records = useMemo(() => {
    if (!Array.isArray(q3.data?.records)) return []
    return q3.data.records
      .map((row) => ({
        round: Number(row.round),
        event: String(row.event_name || ''),
        driver: String(row.driver || ''),
        team: String(row.team || ''),
        gap: Number(row.gap_to_pole_sec),
      }))
      .filter((row) => Number.isFinite(row.round) && Number.isFinite(row.gap))
  }, [q3.data])
  const q3Rounds = useMemo(() => {
    const seen = new Map()
    q3Records.forEach((row) => {
      if (!seen.has(row.round)) seen.set(row.round, { round: row.round, event: row.event })
    })
    return [...seen.values()].sort((a, b) => a.round - b.round)
  }, [q3Records])
  useEffect(() => {
    if (!q3Rounds.length) return
    const latest = q3Rounds[q3Rounds.length - 1].round
    setSelectedQ3Round((prev) => (q3Rounds.some((entry) => entry.round === prev) ? prev : latest))
  }, [q3Rounds])
  const q3RoundRows = useMemo(() => {
    if (!selectedQ3Round) return []
    return q3Records.filter((row) => row.round === selectedQ3Round).sort((a, b) => a.gap - b.gap).slice(0, 12)
  }, [q3Records, selectedQ3Round])

  const conversionRows = useMemo(() => {
    if (!Array.isArray(poleToWin.data?.records)) return []
    return poleToWin.data.records
      .map((row) => ({
        driver: String(row.driver || ''),
        poles: Number(row.poles || 0),
        winsFromPole: Number(row.wins_from_pole || 0),
        conversion: Number(row.conversion_rate || 0),
      }))
      .sort((a, b) => b.conversion - a.conversion || b.poles - a.poles)
  }, [poleToWin.data])

  const paceRounds = useMemo(() => {
    if (!Array.isArray(pace.data?.rounds)) return []
    return pace.data.rounds
      .map((row) => ({ round: Number(row.round), event: String(row.event || '') }))
      .filter((row) => Number.isFinite(row.round))
      .sort((a, b) => a.round - b.round)
  }, [pace.data])
  const paceRows = useMemo(() => {
    if (!Array.isArray(pace.data?.rows)) return []
    return pace.data.rows
      .map((row) => ({
        round: Number(row.round),
        driver: String(row.driver || ''),
        team: String(row.team || ''),
        avg: Number(row.avg_lap_s),
        delta: Number(row.pace_delta_to_best_avg_s),
        consistency: Number(row.consistency_s),
      }))
      .filter((row) => Number.isFinite(row.round) && row.driver)
  }, [pace.data])
  useEffect(() => {
    if (!paceRounds.length) return
    const latest = paceRounds[paceRounds.length - 1].round
    setSelectedPaceRound((prev) => (paceRounds.some((entry) => entry.round === prev) ? prev : latest))
  }, [paceRounds])
  const paceRoundRows = useMemo(() => {
    if (!selectedPaceRound) return []
    const metricKey = paceMetric === 'consistency_s' ? 'consistency' : 'delta'
    return paceRows.filter((row) => row.round === selectedPaceRound).sort((a, b) => Number(a[metricKey]) - Number(b[metricKey])).slice(0, 12)
  }, [paceRows, selectedPaceRound, paceMetric])

  const pitRounds = useMemo(() => {
    if (!Array.isArray(pits.data?.rounds)) return []
    return pits.data.rounds
      .map((row) => ({ round: Number(row.round), event: String(row.event || '') }))
      .filter((row) => Number.isFinite(row.round))
      .sort((a, b) => a.round - b.round)
  }, [pits.data])
  const pitTeamSeason = useMemo(() => {
    if (!Array.isArray(pits.data?.team_season)) return []
    return pits.data.team_season
      .map((row) => ({ team: String(row.team || ''), avg: Number(row.avg_pit_s), consistency: Number(row.consistency_s) }))
      .filter((row) => row.team && Number.isFinite(row.avg))
  }, [pits.data])
  const pitByRound = useMemo(() => {
    if (!Array.isArray(pits.data?.team_by_round)) return []
    return pits.data.team_by_round
      .map((row) => ({ round: Number(row.round), team: String(row.team || ''), p50: Number(row.p50_pit_s), best: Number(row.best_pit_s) }))
      .filter((row) => Number.isFinite(row.round) && row.team)
  }, [pits.data])
  useEffect(() => {
    if (!pitRounds.length) return
    const latest = pitRounds[pitRounds.length - 1].round
    setSelectedPitRound((prev) => (pitRounds.some((entry) => entry.round === prev) ? prev : latest))
  }, [pitRounds])
  const pitRanking = useMemo(() => {
    const metricKey = pitMetric === 'consistency_s' ? 'consistency' : 'avg'
    return [...pitTeamSeason].sort((a, b) => Number(a[metricKey]) - Number(b[metricKey]))
  }, [pitTeamSeason, pitMetric])
  const pitRoundRows = useMemo(() => {
    if (!selectedPitRound) return []
    return pitByRound.filter((row) => row.round === selectedPitRound).sort((a, b) => a.p50 - b.p50)
  }, [pitByRound, selectedPitRound])
  const raceSummary = useMemo(() => {
    if (!Array.isArray(pits.data?.race_summary)) return []
    return pits.data.race_summary
      .map((row) => ({ round: Number(row.round), totalStops: Number(row.total_stops || 0), fastestPit: Number(row.fastest_pit_s) }))
      .filter((row) => Number.isFinite(row.round))
  }, [pits.data])

  const overtakeRaces = useMemo(() => {
    if (!Array.isArray(overtakes.data?.races)) return []
    return overtakes.data.races
      .map((row) => ({
        round: Number(row.round),
        event: String(row.event || ''),
        total: Number(row.total_overtakes || 0),
        passRate: Number(row.pass_rate || 0),
        processional: Number(row.processional_index || 0),
      }))
      .filter((row) => Number.isFinite(row.round))
      .sort((a, b) => a.round - b.round)
  }, [overtakes.data])
  useEffect(() => {
    if (!overtakeRaces.length) return
    const latest = overtakeRaces[overtakeRaces.length - 1].round
    setSelectedOvertakeRound((prev) => (overtakeRaces.some((entry) => entry.round === prev) ? prev : latest))
  }, [overtakeRaces])
  const selectedRace = useMemo(() => overtakeRaces.find((row) => row.round === selectedOvertakeRound) || null, [overtakeRaces, selectedOvertakeRound])
  const circuitIndex = useMemo(() => {
    if (!Array.isArray(overtakes.data?.circuit_index)) return []
    return overtakes.data.circuit_index
      .map((row) => ({ round: Number(row.round), event: String(row.event || ''), processional: Number(row.processional_index || 0) }))
      .sort((a, b) => b.processional - a.processional)
      .slice(0, 8)
  }, [overtakes.data])
  const driverPassing = useMemo(() => {
    if (!Array.isArray(overtakes.data?.driver_passing)) return []
    return overtakes.data.driver_passing
      .map((row) => ({ driver: String(row.driver || ''), team: String(row.team || ''), passes: Number(row.passes_made || 0), net: Number(row.positions_gained_net || 0) }))
      .sort((a, b) => b.passes - a.passes)
      .slice(0, 10)
  }, [overtakes.data])

  const nowReading = CHAPTERS.find((chapter) => chapter.id === activeSection) ?? CHAPTERS[0]
  const chapter1Missing = !standings.loading && !standings.error && !lineData.length
  const chapter2Missing = !q3.loading && !q3.error && !q3RoundRows.length
  const chapter3Missing = !pace.loading && !pace.error && !paceRoundRows.length
  const chapter4Missing = !pits.loading && !pits.error && !pitRanking.length
  const chapter5Missing = !overtakes.loading && !overtakes.error && !overtakeRaces.length

  const overtakeStats = useMemo(() => {
    if (!overtakeRaces.length) return { minTotal: 0, maxTotal: 1, minRate: 0, maxRate: 1 }
    return overtakeRaces.reduce(
      (acc, row) => ({
        minTotal: Math.min(acc.minTotal, row.total),
        maxTotal: Math.max(acc.maxTotal, row.total),
        minRate: Math.min(acc.minRate, row.passRate),
        maxRate: Math.max(acc.maxRate, row.passRate),
      }),
      { minTotal: Infinity, maxTotal: -Infinity, minRate: Infinity, maxRate: -Infinity }
    )
  }, [overtakeRaces])

  return (
    <div className='report-shell' data-spotlight={spotlightMode ? 'on' : 'off'}>
      <div className='ambient ambient-a' />
      <div className='ambient ambient-b' />
      <header className='topbar' ref={navRef}>
        <div className='brand'><p>F1 DATA INTELLIGENCE</p><h1>Report 2025</h1></div>
        <div className='reading-state'><span>Now Reading</span><strong>{nowReading.kicker}: {nowReading.title}</strong><em>{Math.round(scrollProgress * 100)}% through report</em></div>
        <div className='global-actions'>
          <button type='button' className={`chip ${spotlightMode ? 'is-on' : ''}`} onClick={() => setSpotlightMode((prev) => !prev)}>Spotlight {spotlightMode ? 'On' : 'Off'}</button>
          <button type='button' className='chip' onClick={() => setShowMethodology(true)}>Methodology</button>
        </div>
        <nav className='chapter-nav' aria-label='Report chapters'>
          {CHAPTERS.map((chapter) => <button key={chapter.id} type='button' className={`nav-link ${activeSection === chapter.id ? 'is-active' : ''}`} onClick={() => scrollToSection(chapter.id)}>{chapter.navLabel}</button>)}
        </nav>
        <div className='progress-track' aria-hidden='true'><div className='progress-fill' style={{ width: `${Math.round(scrollProgress * 100)}%` }} /></div>
      </header>

      <main className='report-main'>
        <motion.section id='intro' className={`report-section intro ${activeSection === 'intro' ? 'is-active' : ''}`} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <div className='section-head'>
            <p className='kicker'>Editorial Report</p>
            <h2>Season performance, translated into momentum, pace and passing intelligence.</h2>
            <p>Editorial pacing with dense headlines, visual rhythm, and interactive chapter flow. Use the chapter rail, keyboard arrows, or scroll to navigate.</p>
          </div>
          <div className='media-row'>
            <article className='media-card'><MediaTile candidates={getDriverImage(topDrivers[0]?.driver || 'NOR')} label={topDrivers[0]?.driver || 'Driver'} sublabel='Driver portrait' /></article>
            <article className='media-card'><MediaTile candidates={getTeamLogo('McLaren')} label='McLaren' sublabel='Team logo' /></article>
            <article className='media-card'><MediaTile candidates={getCarImage('Ferrari')} label='Ferrari Car' sublabel='Car image' /></article>
          </div>
        </motion.section>

        <section id='chapter-1' className={`report-section ${activeSection === 'chapter-1' ? 'is-active' : ''}`}>
          <div className='section-head'><p className='kicker'>Chapter 1</p><h2>Standings Momentum</h2><p>Who accumulated points with consistency, and where the season tilted.</p></div>
          <ChapterStatus loading={standings.loading || heatmap.loading} error={standings.error || heatmap.error} missingText={chapter1Missing ? 'Missing fields in chapter 1 JSON payloads.' : ''} />
          {!standings.loading && !heatmap.loading && !(standings.error || heatmap.error) && !chapter1Missing ? (
            <>
              <article className='panel-card'>
                <div className='card-head'><h3>Cumulative points arc</h3><span>Top 6 at season end</span></div>
                <div className='chart-box'><ResponsiveContainer width='100%' height={360}><AreaChart data={lineData}><defs><linearGradient id='arcFill' x1='0' y1='0' x2='0' y2='1'><stop offset='5%' stopColor='#ff5500' stopOpacity={0.35} /><stop offset='95%' stopColor='#ff5500' stopOpacity={0} /></linearGradient></defs><CartesianGrid strokeDasharray='3 8' stroke='rgba(255,255,255,0.15)' /><XAxis dataKey='round' stroke='rgba(255,255,255,0.6)' /><YAxis stroke='rgba(255,255,255,0.6)' /><Tooltip contentStyle={{ backgroundColor: 'rgba(10,10,10,0.95)', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12 }} /><Area type='monotone' dataKey={topDrivers[0]?.driver} stroke='#ff5500' fill='url(#arcFill)' strokeWidth={2.8} />{topDrivers.slice(1).map((driver, index) => <Line key={driver.driver} type='monotone' dataKey={driver.driver} stroke={SERIES_COLORS[index + 1]} strokeWidth={2} dot={false} />)}</AreaChart></ResponsiveContainer></div>
              </article>
              <article className='panel-card'>
                <div className='card-head'><h3>Round points heat texture</h3><span>Top drivers only</span></div>
                <div className='heatmap-grid'><div className='heatmap-row heatmap-header'><span>Driver</span>{heatmapRounds.map((round) => <span key={`h-round-${round.RoundNumber}`}>{round.RoundNumber}</span>)}</div>{miniHeatmapRows.map((row) => <div className='heatmap-row' key={`h-row-${row.Driver}`}><span>{row.Driver}</span>{heatmapRounds.map((round) => { const value = Number(row[String(round.RoundNumber)] || 0); const alpha = heatMax > 0 ? scale(value, 0, heatMax, 0.08, 1) : 0.08; return <i key={`h-${row.Driver}-${round.RoundNumber}`} style={{ backgroundColor: `rgba(255, 85, 0, ${alpha})` }} title={`R${round.RoundNumber}: ${value} pts`} /> })}</div>)}</div>
              </article>
            </>
          ) : null}
        </section>

        <section id='chapter-2' className={`report-section ${activeSection === 'chapter-2' ? 'is-active' : ''}`}>
          <div className='section-head'><p className='kicker'>Chapter 2</p><h2>Qualifying Edge</h2><p>Micro margins in Q3 and who converted pole into race control.</p></div>
          <ChapterStatus loading={q3.loading || poleToWin.loading} error={q3.error || poleToWin.error} missingText={chapter2Missing ? 'Missing fields in chapter 2 JSON payloads.' : ''} />
          {!q3.loading && !poleToWin.loading && !(q3.error || poleToWin.error) && !chapter2Missing ? (
            <>
              <article className='panel-card'>
                <div className='card-head split'><div><h3>Q3 spread by round</h3><span>Gap to pole in selected session</span></div><label className='control'><span>Round</span><select value={selectedQ3Round ?? ''} onChange={(event) => setSelectedQ3Round(Number(event.target.value))}>{q3Rounds.map((round) => <option key={`q3-r-${round.round}`} value={round.round}>R{round.round} - {compactEventName(round.event)}</option>)}</select></label></div>
                <div className='chart-box'><ResponsiveContainer width='100%' height={360}><BarChart data={q3RoundRows} layout='vertical'><CartesianGrid strokeDasharray='3 8' stroke='rgba(255,255,255,0.15)' /><XAxis type='number' stroke='rgba(255,255,255,0.6)' tickFormatter={(value) => `${Number(value).toFixed(3)}s`} /><YAxis type='category' dataKey='driver' width={48} stroke='rgba(255,255,255,0.6)' /><Tooltip formatter={(value) => [`${Number(value).toFixed(3)}s`, 'Gap to pole']} contentStyle={{ backgroundColor: 'rgba(10,10,10,0.95)', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12 }} labelStyle={{ color: '#f9f8f5' }} itemStyle={{ color: '#f9f8f5' }} /><Bar dataKey='gap' radius={[0, 9, 9, 0]}>{q3RoundRows.map((entry, index) => <Cell key={`q3-cell-${entry.driver}`} fill={SERIES_COLORS[index % SERIES_COLORS.length]} />)}</Bar></BarChart></ResponsiveContainer></div>
              </article>
              <article className='panel-card'><div className='card-head'><h3>Pole conversion ledger</h3><span>Win rate from pole starts</span></div><div className='ledger-grid'>{conversionRows.map((row, index) => <div key={`conv-${row.driver}`} className='ledger-row'><div className='ledger-driver'><MediaTile candidates={getDriverImage(row.driver)} label={row.driver} sublabel={row.driver} /><p>{row.driver}</p></div><div className='ledger-bar-wrap'><div className='ledger-bar' style={{ width: `${clamp(row.conversion * 100, 0, 100)}%`, background: SERIES_COLORS[index % SERIES_COLORS.length] }} /></div><strong>{Math.round(row.conversion * 100)}%</strong></div>)}</div></article>
            </>
          ) : null}
        </section>

        <section id='chapter-3' className={`report-section ${activeSection === 'chapter-3' ? 'is-active' : ''}`}>
          <div className='section-head'><p className='kicker'>Chapter 3</p><h2>Race Pace Reality</h2><p>Raw lap-speed truth and consistency over race distance.</p></div>
          <ChapterStatus loading={pace.loading} error={pace.error} missingText={chapter3Missing ? 'Missing fields in chapter 3 JSON payload.' : ''} />
          {!pace.loading && !pace.error && !chapter3Missing ? (
            <article className='panel-card'>
              <div className='card-head split'><div><h3>Stint-level pace table</h3><span>Top drivers by selected metric</span></div><div className='control-stack'><label className='control'><span>Round</span><select value={selectedPaceRound ?? ''} onChange={(event) => setSelectedPaceRound(Number(event.target.value))}>{paceRounds.map((round) => <option key={`pace-r-${round.round}`} value={round.round}>R{round.round} - {compactEventName(round.event)}</option>)}</select></label><div className='toggle'><button type='button' className={paceMetric === 'pace_delta_to_best_avg_s' ? 'is-active' : ''} onClick={() => setPaceMetric('pace_delta_to_best_avg_s')}>Delta</button><button type='button' className={paceMetric === 'consistency_s' ? 'is-active' : ''} onClick={() => setPaceMetric('consistency_s')}>Consistency</button></div></div></div>
              <div className='chart-box'><ResponsiveContainer width='100%' height={380}><BarChart data={paceRoundRows} layout='vertical'><CartesianGrid strokeDasharray='3 8' stroke='rgba(255,255,255,0.15)' /><XAxis type='number' stroke='rgba(255,255,255,0.6)' tickFormatter={(value) => `${Number(value).toFixed(3)}s`} /><YAxis type='category' dataKey='driver' width={54} stroke='rgba(255,255,255,0.6)' /><Tooltip formatter={(value) => [`${Number(value).toFixed(3)}s`, paceMetric === 'consistency_s' ? 'Consistency' : 'Delta']} contentStyle={{ backgroundColor: 'rgba(10,10,10,0.95)', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12 }} /><Bar dataKey={paceMetric === 'consistency_s' ? 'consistency' : 'delta'} radius={[0, 9, 9, 0]} fill='#ff5500' /></BarChart></ResponsiveContainer></div>
            </article>
          ) : null}
        </section>

        <section id='chapter-4' className={`report-section ${activeSection === 'chapter-4' ? 'is-active' : ''}`}>
          <div className='section-head'><p className='kicker'>Chapter 4</p><h2>Pit Stop Intelligence</h2><p>Execution speed, repeatability, and race-window volatility.</p></div>
          <ChapterStatus loading={pits.loading} error={pits.error} missingText={chapter4Missing ? 'Missing fields in chapter 4 JSON payload.' : ''} />
          {!pits.loading && !pits.error && !chapter4Missing ? (
            <>
              <article className='panel-card'><div className='card-head split'><div><h3>Season pit ranking</h3><span>Across all teams and stops</span></div><div className='toggle'><button type='button' className={pitMetric === 'avg_pit_s' ? 'is-active' : ''} onClick={() => setPitMetric('avg_pit_s')}>Average</button><button type='button' className={pitMetric === 'consistency_s' ? 'is-active' : ''} onClick={() => setPitMetric('consistency_s')}>Consistency</button></div></div><div className='chart-box'><ResponsiveContainer width='100%' height={360}><BarChart data={pitRanking} layout='vertical'><CartesianGrid strokeDasharray='3 8' stroke='rgba(255,255,255,0.15)' /><XAxis type='number' stroke='rgba(255,255,255,0.6)' tickFormatter={(value) => `${Number(value).toFixed(2)}s`} /><YAxis type='category' dataKey='team' width={120} stroke='rgba(255,255,255,0.6)' /><Tooltip formatter={(value) => [`${Number(value).toFixed(3)}s`, pitMetric === 'consistency_s' ? 'Consistency' : 'Average']} contentStyle={{ backgroundColor: 'rgba(10,10,10,0.95)', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12 }} /><Bar dataKey={pitMetric === 'consistency_s' ? 'consistency' : 'avg'} radius={[0, 9, 9, 0]}>{pitRanking.map((row, index) => <Cell key={`pit-${row.team}`} fill={SERIES_COLORS[index % SERIES_COLORS.length]} />)}</Bar></BarChart></ResponsiveContainer></div></article>
              <article className='panel-card'><div className='card-head split'><div><h3>Race volatility profile</h3><span>Median vs best pit in selected round</span></div><label className='control'><span>Round</span><select value={selectedPitRound ?? ''} onChange={(event) => setSelectedPitRound(Number(event.target.value))}>{pitRounds.map((round) => <option key={`pit-r-${round.round}`} value={round.round}>R{round.round} - {compactEventName(round.event)}</option>)}</select></label></div><div className='chart-box'><ResponsiveContainer width='100%' height={360}><ComposedChart data={pitRoundRows}><CartesianGrid strokeDasharray='3 8' stroke='rgba(255,255,255,0.15)' /><XAxis dataKey='team' stroke='rgba(255,255,255,0.6)' /><YAxis stroke='rgba(255,255,255,0.6)' tickFormatter={(value) => `${Number(value).toFixed(2)}s`} /><Tooltip contentStyle={{ backgroundColor: 'rgba(10,10,10,0.95)', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 12 }} formatter={(value) => `${Number(value).toFixed(3)}s`} /><Bar dataKey='p50' fill='#ff5500' radius={[8, 8, 0, 0]} /><Line type='monotone' dataKey='best' stroke='#8ad0ff' strokeWidth={2.4} dot={{ r: 2.4 }} /></ComposedChart></ResponsiveContainer></div><div className='chip-list'>{pitRanking.slice(0, 5).map((entry) => <span className='tag' key={`team-tag-${entry.team}`} title={entry.team}><div className='abbr-avatar'>{String(entry.team || '').replace(/[^A-Za-z]/g, '').slice(0, 3).toUpperCase()}</div></span>)}</div></article>
              <article className='stat-grid'><div className='stat-card'><span>Total stops</span><strong>{raceSummary.reduce((sum, row) => sum + row.totalStops, 0)}</strong></div><div className='stat-card'><span>Fastest pit (season)</span><strong>{raceSummary.length ? `${Math.min(...raceSummary.map((row) => row.fastestPit)).toFixed(3)}s` : 'n/a'}</strong></div><div className='stat-card'><span>Teams tracked</span><strong>{pitRanking.length}</strong></div></article>
            </>
          ) : null}
        </section>

        <section id='chapter-5' className={`report-section ${activeSection === 'chapter-5' ? 'is-active' : ''}`}>
          <div className='section-head'><p className='kicker'>Chapter 5</p><h2>The Overtake Report</h2><p>Race-level passing intensity and season-long aggressors.</p></div>
          <ChapterStatus loading={overtakes.loading} error={overtakes.error} missingText={chapter5Missing ? 'Missing fields in chapter 5 JSON payload.' : ''} />
          {!overtakes.loading && !overtakes.error && !chapter5Missing ? (
            <>
              <article className='panel-card'><div className='card-head'><h3>Overtake pulse strip</h3><span>Tap a dot to view race info</span></div><div className='pulse-wrap'><div className='pulse-strip-simple'>{overtakeRaces.map((race) => { const radius = scale(race.total, overtakeStats.minTotal, overtakeStats.maxTotal, 14, 40); const alpha = scale(race.passRate, overtakeStats.minRate, overtakeStats.maxRate, 0.35, 1); const selected = race.round === selectedOvertakeRound; return <button key={`pulse-${race.round}`} type='button' className={`pulse-dot-btn ${selected ? 'is-active' : ''}`} style={{ width: `${radius}px`, height: `${radius}px`, backgroundColor: `rgba(255,85,0,${alpha.toFixed(3)})` }} onClick={() => setSelectedOvertakeRound(race.round)} onPointerDown={() => setSelectedOvertakeRound(race.round)} aria-label={`Round ${race.round} ${compactEventName(race.event)}`} /> })}</div><div className='status-card pulse-note'>{selectedRace ? `R${selectedRace.round} ${compactEventName(selectedRace.event)} | overtakes ${selectedRace.total} | pass rate ${selectedRace.passRate.toFixed(4)} | processional ${selectedRace.processional}` : 'Tap a race dot to inspect'}</div></div></article>
              <article className='panel-card'><div className='card-head'><h3>Most processional races</h3><span>Higher index means harder to pass</span></div><div className='poster-grid'>{circuitIndex.map((race) => <button key={`ci-${race.round}`} type='button' className={`poster ${selectedOvertakeRound === race.round ? 'is-active' : ''}`} onClick={() => setSelectedOvertakeRound(race.round)}><span>R{race.round}</span><strong>{compactEventName(race.event)}</strong><em>{race.processional}</em></button>)}</div></article>
              <article className='panel-card'><div className='card-head'><h3>Driver passing profiles</h3><span>Season totals for overtakes and net positions</span></div><div className='profile-list'>{driverPassing.map((row) => <div key={`pass-${row.driver}`} className='profile-row'><div className='profile-driver'><div className='abbr-avatar'>{String(row.driver || '').slice(0, 3).toUpperCase()}</div><div><p>{row.driver}</p><span>{row.team}</span></div></div><div className='profile-meter'><i style={{ width: `${clamp((row.passes / Math.max(...driverPassing.map((entry) => entry.passes))), 0, 1) * 100}%` }} /></div><strong>{row.passes}</strong><em>{row.net >= 0 ? `+${row.net}` : row.net}</em></div>)}</div></article>
            </>
          ) : null}
        </section>
      </main>

      <aside className={`methodology ${showMethodology ? 'is-open' : ''}`} aria-hidden={!showMethodology}>
        <div className='methodology-head'><h3>Methodology</h3><button type='button' className='chip' onClick={() => setShowMethodology(false)}>Close</button></div>
        <p>Data source: local JSON exports in public/data generated by the Python pipeline.</p>
        <p>Design objective: editorial narrative pacing with chapter-level interactions and resilient media fallbacks.</p>
        <p>Navigation: sticky chapter rail, active sync on scroll, and keyboard arrows for previous/next chapter jumps.</p>
        <p>Missing files: each chapter reports loading/data errors in-place and keeps the rest of the report functional.</p>
      </aside>
      <div className={`drawer-backdrop ${showMethodology ? 'is-open' : ''}`} onClick={() => setShowMethodology(false)} />
    </div>
  )
}

export default App
