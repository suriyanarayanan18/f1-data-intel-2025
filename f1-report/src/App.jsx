import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './App.css'

const CHAPTERS = [
  {
    id: 'chapter-1',
    label: 'Chapter 1',
    title: 'Standings Momentum',
    deck: 'How the title fight evolved week by week through cumulative points and race-level scoring intensity.',
  },
  {
    id: 'chapter-2',
    label: 'Chapter 2',
    title: 'Qualifying Edge',
    deck: 'How close the grid really was in Q3, and which pole sitters converted clean starts into race wins.',
  },
]

const NAV_ITEMS = [{ id: 'intro', label: 'Intro' }, ...CHAPTERS.map((chapter) => ({ id: chapter.id, label: chapter.label }))]

const SERIES_COLORS = ['#ff6b2b', '#ff8a54', '#ffc17e', '#6fc3ff', '#49a9f8', '#c1e4ff', '#ffd35f', '#8ce4bf', '#f3a0a0', '#d7b8ff']

function compactEventName(name) {
  return String(name || '').replace(' Grand Prix', '').replace('Emilia Romagna', 'Imola')
}

function getSeriesColor(index) {
  return SERIES_COLORS[index % SERIES_COLORS.length]
}

function ChapterStatus({ loading, error, missingText }) {
  if (loading) {
    return <div className="status-card">Loading chapter data...</div>
  }

  if (error) {
    return <div className="status-card status-error">{error}</div>
  }

  if (missingText) {
    return <div className="status-card status-error">{missingText}</div>
  }

  return null
}

function App() {
  const [activeSection, setActiveSection] = useState('intro')
  const [chapter1Loading, setChapter1Loading] = useState(true)
  const [chapter1Error, setChapter1Error] = useState('')
  const [standingsData, setStandingsData] = useState(null)
  const [heatmapData, setHeatmapData] = useState(null)

  const [chapter2Loading, setChapter2Loading] = useState(true)
  const [chapter2Error, setChapter2Error] = useState('')
  const [q3Data, setQ3Data] = useState(null)
  const [poleToWinData, setPoleToWinData] = useState(null)
  const [selectedRound, setSelectedRound] = useState(null)

  const navRef = useRef(null)

  useEffect(() => {
    let mounted = true

    async function loadChapter1() {
      setChapter1Loading(true)
      setChapter1Error('')

      try {
        const [standingsRes, heatmapRes] = await Promise.all([
          fetch('/data/standings_progression.json'),
          fetch('/data/points_heatmap.json'),
        ])

        if (!standingsRes.ok || !heatmapRes.ok) {
          throw new Error('Chapter 1 datasets could not be loaded.')
        }

        const [standingsJson, heatmapJson] = await Promise.all([
          standingsRes.json(),
          heatmapRes.json(),
        ])

        if (mounted) {
          setStandingsData(standingsJson)
          setHeatmapData(heatmapJson)
        }
      } catch (err) {
        if (mounted) {
          setChapter1Error(err instanceof Error ? err.message : 'Failed loading chapter 1 data.')
        }
      } finally {
        if (mounted) {
          setChapter1Loading(false)
        }
      }
    }

    loadChapter1()

    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    let mounted = true

    async function loadChapter2() {
      setChapter2Loading(true)
      setChapter2Error('')

      try {
        const [q3Res, poleRes] = await Promise.all([
          fetch('/data/q3_gaps.json'),
          fetch('/data/pole_to_win.json'),
        ])

        if (!q3Res.ok || !poleRes.ok) {
          throw new Error('Chapter 2 datasets could not be loaded.')
        }

        const [q3Json, poleJson] = await Promise.all([q3Res.json(), poleRes.json()])

        if (mounted) {
          setQ3Data(q3Json)
          setPoleToWinData(poleJson)
        }
      } catch (err) {
        if (mounted) {
          setChapter2Error(err instanceof Error ? err.message : 'Failed loading chapter 2 data.')
        }
      } finally {
        if (mounted) {
          setChapter2Loading(false)
        }
      }
    }

    loadChapter2()

    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    function syncActiveSection() {
      const navHeight = navRef.current?.getBoundingClientRect().height ?? 0
      const marker = window.scrollY + navHeight + window.innerHeight * 0.38

      let current = NAV_ITEMS[0].id
      NAV_ITEMS.forEach((item) => {
        const el = document.getElementById(item.id)
        if (el && el.offsetTop <= marker) {
          current = item.id
        }
      })

      setActiveSection(current)
    }

    syncActiveSection()
    window.addEventListener('scroll', syncActiveSection, { passive: true })
    window.addEventListener('resize', syncActiveSection)

    return () => {
      window.removeEventListener('scroll', syncActiveSection)
      window.removeEventListener('resize', syncActiveSection)
    }
  }, [])

  const standingsRounds = useMemo(() => {
    return Array.isArray(standingsData?.rounds) ? standingsData.rounds : []
  }, [standingsData])

  const topDrivers = useMemo(() => {
    if (!Array.isArray(standingsData?.rows) || !standingsRounds.length) {
      return []
    }

    const finalRound = String(standingsRounds[standingsRounds.length - 1].RoundNumber)
    return [...standingsData.rows]
      .sort((a, b) => Number(b[finalRound] ?? 0) - Number(a[finalRound] ?? 0))
      .slice(0, 10)
  }, [standingsData, standingsRounds])

  const lineData = useMemo(() => {
    if (!standingsRounds.length || !topDrivers.length) {
      return []
    }

    return standingsRounds.map((round) => {
      const key = String(round.RoundNumber)
      const row = {
        round: round.RoundNumber,
        event: compactEventName(round.EventName),
      }

      topDrivers.forEach((driver) => {
        row[driver.Driver] = Number(driver[key] ?? 0)
      })

      return row
    })
  }, [standingsRounds, topDrivers])

  const heatmapRows = useMemo(() => {
    return Array.isArray(heatmapData?.rows) ? heatmapData.rows : []
  }, [heatmapData])

  const heatmapRounds = useMemo(() => {
    return Array.isArray(heatmapData?.rounds) ? heatmapData.rounds : []
  }, [heatmapData])

  const heatmapMax = useMemo(() => {
    if (!heatmapRows.length || !heatmapRounds.length) {
      return 0
    }

    return heatmapRows.reduce((maxVal, row) => {
      return heatmapRounds.reduce((acc, round) => {
        const value = Number(row[String(round.RoundNumber)] ?? 0)
        return value > acc ? value : acc
      }, maxVal)
    }, 0)
  }, [heatmapRows, heatmapRounds])

  const q3Records = useMemo(() => {
    if (!Array.isArray(q3Data?.records)) {
      return []
    }

    return q3Data.records
      .map((record) => ({
        ...record,
        round: Number(record.round),
        gap_to_pole_sec: Number(record.gap_to_pole_sec),
      }))
      .filter((record) => Number.isFinite(record.round) && Number.isFinite(record.gap_to_pole_sec))
  }, [q3Data])

  const q3Rounds = useMemo(() => {
    const map = new Map()

    q3Records.forEach((record) => {
      if (!map.has(record.round)) {
        map.set(record.round, { round: record.round, event_name: record.event_name })
      }
    })

    return [...map.values()].sort((a, b) => a.round - b.round)
  }, [q3Records])

  useEffect(() => {
    if (!q3Rounds.length) {
      return
    }

    const latestRound = q3Rounds[q3Rounds.length - 1].round
    setSelectedRound((prev) => (q3Rounds.some((entry) => entry.round === prev) ? prev : latestRound))
  }, [q3Rounds])

  const selectedRoundRows = useMemo(() => {
    if (!selectedRound) {
      return []
    }

    return q3Records
      .filter((record) => record.round === selectedRound)
      .sort((a, b) => a.gap_to_pole_sec - b.gap_to_pole_sec)
  }, [q3Records, selectedRound])

  const conversionRows = useMemo(() => {
    if (!Array.isArray(poleToWinData?.records)) {
      return []
    }

    return poleToWinData.records
      .map((row) => ({
        ...row,
        poles: Number(row.poles) || 0,
        wins_from_pole: Number(row.wins_from_pole) || 0,
        conversion_rate: Number(row.conversion_rate) || 0,
      }))
      .sort((a, b) => b.conversion_rate - a.conversion_rate || b.poles - a.poles)
  }, [poleToWinData])

  function scrollToSection(id) {
    const target = document.getElementById(id)
    if (!target) {
      return
    }

    const navHeight = navRef.current?.getBoundingClientRect().height ?? 0
    const y = window.scrollY + target.getBoundingClientRect().top - navHeight - 16
    window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' })
  }

  const chapter1Missing = !chapter1Loading && !chapter1Error && (!lineData.length || !heatmapRows.length)
  const chapter2Missing = !chapter2Loading && !chapter2Error && (!q3Records.length || !conversionRows.length)

  return (
    <div className="editorial-shell">
      <header ref={navRef} className="sticky-nav">
        <div className="brand-block">
          <p>F1 DATA INTEL</p>
          <span>2025 report</span>
        </div>
        <nav className="chapter-nav" aria-label="Report chapters">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className={activeSection === item.id ? 'is-active' : ''}
              onClick={(event) => {
                event.preventDefault()
                scrollToSection(item.id)
              }}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </header>

      <main>
        <section id="intro" className="intro-panel">
          <p className="eyebrow">Interactive Editorial</p>
          <h1>Soundtrack of a season.</h1>
          <p>
            Scroll chapter by chapter through standings momentum and qualifying execution. Each section loads directly from
            your generated JSON exports in `/data`.
          </p>
          <button type="button" onClick={() => scrollToSection('chapter-1')}>
            Start report
          </button>
        </section>

        <section id="chapter-1" className="chapter-panel" aria-labelledby="chapter-1-title">
          <div className="chapter-header">
            <p className="chapter-kicker">Chapter 1</p>
            <h2 id="chapter-1-title">Standings Momentum</h2>
            <p>{CHAPTERS[0].deck}</p>
          </div>

          <ChapterStatus
            loading={chapter1Loading}
            error={chapter1Error}
            missingText={chapter1Missing ? 'Missing fields in chapter 1 JSON payloads.' : ''}
          />

          {!chapter1Loading && !chapter1Error && !chapter1Missing ? (
            <>
              <article className="panel-card">
                <div className="card-headline">
                  <h3>Cumulative points trajectory</h3>
                  <span>Top 10 drivers by final standings</span>
                </div>
                <div className="chart-box" role="img" aria-label="Line chart showing cumulative points by round">
                  <ResponsiveContainer width="100%" height={400}>
                    <LineChart data={lineData} margin={{ top: 12, right: 18, left: 8, bottom: 6 }}>
                      <CartesianGrid strokeDasharray="2 8" stroke="rgba(255,255,255,0.12)" />
                      <XAxis dataKey="round" stroke="#90a1b2" tickLine={false} axisLine={{ stroke: 'rgba(255,255,255,0.2)' }} />
                      <YAxis stroke="#90a1b2" tickLine={false} axisLine={{ stroke: 'rgba(255,255,255,0.2)' }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(8,12,18,0.96)',
                          border: '1px solid rgba(255,255,255,0.2)',
                          borderRadius: '14px',
                        }}
                        formatter={(value) => [Number(value).toFixed(0), 'Points']}
                        labelFormatter={(round, payload) => {
                          const event = payload?.[0]?.payload?.event
                          return event ? `R${round} - ${event}` : `Round ${round}`
                        }}
                      />
                      {topDrivers.map((driver, index) => (
                        <Line
                          key={driver.Driver}
                          type="monotone"
                          dataKey={driver.Driver}
                          stroke={getSeriesColor(index)}
                          strokeWidth={2.1}
                          dot={false}
                          activeDot={{ r: 3.8 }}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </article>

              <article className="panel-card">
                <div className="card-headline">
                  <h3>Race-by-race points heatmap</h3>
                  <span>Driver x round matrix</span>
                </div>
                <div className="heatmap-wrap">
                  <table className="heatmap-table">
                    <thead>
                      <tr>
                        <th>Driver</th>
                        {heatmapRounds.map((round) => (
                          <th key={`h-head-${round.RoundNumber}`} title={round.EventName}>
                            R{round.RoundNumber}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {heatmapRows.map((row) => (
                        <tr key={`h-row-${row.Driver}`}>
                          <th>{row.Driver}</th>
                          {heatmapRounds.map((round) => {
                            const key = String(round.RoundNumber)
                            const value = Number(row[key] ?? 0)
                            const alpha = heatmapMax > 0 ? Math.max(0.09, value / heatmapMax) : 0.09

                            return (
                              <td
                                key={`h-cell-${row.Driver}-${key}`}
                                style={{ backgroundColor: `rgba(255, 107, 43, ${alpha})` }}
                                title={`${row.Driver} | ${round.EventName}: ${value} pts`}
                              >
                                {value > 0 ? value : ''}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </>
          ) : null}
        </section>

        <section id="chapter-2" className="chapter-panel" aria-labelledby="chapter-2-title">
          <div className="chapter-header">
            <p className="chapter-kicker">Chapter 2</p>
            <h2 id="chapter-2-title">Qualifying Edge</h2>
            <p>{CHAPTERS[1].deck}</p>
          </div>

          <ChapterStatus
            loading={chapter2Loading}
            error={chapter2Error}
            missingText={chapter2Missing ? 'Missing fields in chapter 2 JSON payloads.' : ''}
          />

          {!chapter2Loading && !chapter2Error && !chapter2Missing ? (
            <>
              <article className="panel-card">
                <div className="card-headline split-headline">
                  <div>
                    <h3>Q3 gap to pole by round</h3>
                    <span>Horizontal ranking for selected event</span>
                  </div>
                  <label className="round-control" htmlFor="round-select">
                    <span>Select round</span>
                    <select
                      id="round-select"
                      value={selectedRound ?? ''}
                      onChange={(event) => setSelectedRound(Number(event.target.value))}
                    >
                      {q3Rounds.map((round) => (
                        <option key={`q3-round-${round.round}`} value={round.round}>
                          R{round.round} - {compactEventName(round.event_name)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="chart-box" role="img" aria-label="Horizontal bar chart of Q3 gaps to pole">
                  <ResponsiveContainer width="100%" height={430}>
                    <BarChart layout="vertical" data={selectedRoundRows} margin={{ top: 6, right: 24, left: 8, bottom: 6 }}>
                      <CartesianGrid strokeDasharray="2 8" stroke="rgba(255,255,255,0.12)" />
                      <XAxis
                        type="number"
                        stroke="#90a1b2"
                        tickLine={false}
                        axisLine={{ stroke: 'rgba(255,255,255,0.2)' }}
                        tickFormatter={(value) => `${Number(value).toFixed(3)}s`}
                      />
                      <YAxis
                        type="category"
                        dataKey="driver"
                        width={52}
                        stroke="#90a1b2"
                        tickLine={false}
                        axisLine={{ stroke: 'rgba(255,255,255,0.2)' }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(8,12,18,0.96)',
                          border: '1px solid rgba(255,255,255,0.2)',
                          borderRadius: '14px',
                        }}
                        formatter={(value) => [`${Number(value).toFixed(3)}s`, 'Gap to pole']}
                      />
                      <Bar dataKey="gap_to_pole_sec" radius={[0, 8, 8, 0]}>
                        {selectedRoundRows.map((entry, index) => (
                          <Cell key={`q3-cell-${entry.driver}`} fill={getSeriesColor(index)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </article>

              <article className="panel-card">
                <div className="card-headline">
                  <h3>Pole-to-win conversion leaderboard</h3>
                  <span>Poles, wins from pole, conversion rate</span>
                </div>
                <div className="table-wrap">
                  <table className="leaderboard-table">
                    <thead>
                      <tr>
                        <th>Driver</th>
                        <th>Poles</th>
                        <th>Wins from pole</th>
                        <th>Conversion</th>
                      </tr>
                    </thead>
                    <tbody>
                      {conversionRows.map((row) => (
                        <tr key={`leaderboard-${row.driver}`}>
                          <th>{row.driver}</th>
                          <td>{row.poles}</td>
                          <td>{row.wins_from_pole}</td>
                          <td>{(row.conversion_rate * 100).toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </>
          ) : null}
        </section>
      </main>
    </div>
  )
}

export default App
