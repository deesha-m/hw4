import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { fetchWeather, type WeatherPick } from '../api.ts'
import { useAuth } from '../auth.tsx'
import { COLLEGES, useCollege } from '../college.tsx'
import { useToast } from '../toast.tsx'

const links = [
  { to: '/', label: 'Home' },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

export default function NavBar() {
  const { user, loading, logOut } = useAuth()
  const { college, setCollege } = useCollege()
  const { notify } = useToast()
  const navigate = useNavigate()
  const [weather, setWeather] = useState<WeatherPick | null>(null)

  useEffect(() => {
    fetchWeather().then(setWeather)
  }, [])

  async function handleLogOut() {
    const name = user?.first_name
    await logOut()
    navigate('/')
    notify(`You're logged out${name ? `, ${name}` : ''}.`, 'Your chat is saved for next time. See you on Broadway.')
  }

  function handleCollege(name: string) {
    setCollege(name || null)
    notify(
      name ? `${name} mode on` : 'College mode off',
      name ? `We'll put ${name} pieces first.` : 'Back to the full Yale shop.',
    )
  }

  return (
    <header className="site-header">
      <div className="announce">
        <span>Officially licensed Yale apparel</span>
        <span className="announce-dot" aria-hidden="true">◆</span>
        <span>57 Broadway, New Haven</span>
        {weather && (
          <>
            <span className="announce-dot" aria-hidden="true">◆</span>
            <span>
              {weather.temperature_f}°F &amp; {weather.condition} on Broadway
            </span>
          </>
        )}
      </div>
      <div className="nav">
        <Link to="/" className="brand" aria-label="Campus Customs home">
          <span className="brand-seal" aria-hidden="true">CC</span>
          <span className="brand-text">
            Campus<span>Customs</span>
            <small>57 Broadway · New Haven</small>
          </span>
        </Link>
        <nav className="nav-links">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === '/'} className="stitch">
              {link.label}
            </NavLink>
          ))}
          <label className="college-picker">
            <span className="visually-hidden">Residential college</span>
            <select value={college ?? ''} onChange={(e) => handleCollege(e.target.value)}>
              <option value="">Your college…</option>
              {COLLEGES.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          {!loading && user && (
            <>
              <span className="nav-user">Hi, {user.first_name}</span>
              <button type="button" className="nav-cta" onClick={handleLogOut}>
                Log Out
              </button>
            </>
          )}
          {!loading && !user && (
            <>
              <NavLink to="/login" className="stitch">
                Log In
              </NavLink>
              <NavLink to="/create-account" className="nav-cta">
                Create Account
              </NavLink>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
