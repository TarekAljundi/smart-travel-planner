const BASE = ''

async function safeJson(res) {
  const text = await res.text()
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(text || `Server returned ${res.status} without valid JSON`)
  }
}

export async function register(email, password) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  const data = await safeJson(res)
  if (!res.ok) throw new Error(data.detail || 'Registration failed')
  return data
}

export async function login(email, password) {
  const res = await fetch(`${BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  const data = await safeJson(res)
  if (!res.ok) throw new Error(data.detail || 'Login failed')
  return data
}

export function streamTripPlan(token, query, onEvent, onDone, onError) {
  const url = `${BASE}/api/plan-trip?query=${encodeURIComponent(query)}&token=${token}`
  const eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    if (event.data === '[DONE]') {
      eventSource.close()
      onDone()
      return
    }
    try {
      const payload = JSON.parse(event.data)
      onEvent(payload)
    } catch (err) {
      // ignore malformed events
    }
  }

  eventSource.onerror = (err) => {
    eventSource.close()
    onError(err)
  }

  return eventSource
}