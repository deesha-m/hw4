import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.tsx'
import { useToast } from '../toast.tsx'
import type { RegisterInput } from '../api.ts'

const MIN_PASSWORD = 8

const empty: RegisterInput = {
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  confirm_password: '',
}

export default function CreateAccount() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const { notify } = useToast()
  const [form, setForm] = useState<RegisterInput>(empty)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user && !submitting) return <Navigate to="/" replace />

  const update = (field: keyof RegisterInput) => (event: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [field]: event.target.value })

  const mismatch = form.confirm_password !== '' && form.password !== form.confirm_password

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (form.password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters`)
      return
    }
    if (form.password !== form.confirm_password) {
      setError("Passwords don't match")
      return
    }
    setSubmitting(true)
    try {
      const created = await register(form)
      navigate('/')
      notify(`Welcome to Campus Customs, ${created.first_name}.`, 'Your chats will now be saved to your account.')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="section auth">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Join Campus Customs</h1>
        <p className="muted">Save your chats and get help finding the right fit.</p>
        <div className="row">
          <label>
            First name
            <input required autoComplete="given-name" value={form.first_name} onChange={update('first_name')} />
          </label>
          <label>
            Last name
            <input required autoComplete="family-name" value={form.last_name} onChange={update('last_name')} />
          </label>
        </div>
        <label>
          Email
          <input
            type="email"
            required
            autoComplete="email"
            placeholder="you@yale.edu"
            value={form.email}
            onChange={update('email')}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={MIN_PASSWORD}
            autoComplete="new-password"
            value={form.password}
            onChange={update('password')}
          />
          <span className="hint">At least {MIN_PASSWORD} characters</span>
        </label>
        <label>
          Confirm password
          <input
            type="password"
            required
            autoComplete="new-password"
            value={form.confirm_password}
            onChange={update('confirm_password')}
            aria-invalid={mismatch}
          />
          {mismatch && <span className="hint error">Passwords don't match</span>}
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" className="button" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create Account'}
        </button>
        <p className="muted">
          Already have an account? <Link to="/login" className="text-link">Log in</Link>
        </p>
      </form>
    </section>
  )
}
