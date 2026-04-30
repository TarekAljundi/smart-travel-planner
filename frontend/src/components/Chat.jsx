import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { streamTripPlan } from '../services/api'
import ToolCallList from './ToolCallList'

/* =====================================================
   Ultimate section splitter – works on ANY text
   ===================================================== */
const SECTION_HEADERS = [
  'RECOMMENDED DESTINATION',
  'CURRENT WEATHER',
  '2-WEEK ITINERARY',
  'BUDGET BREAKDOWN',
  'IMPORTANT CAVEATS',
]

function splitIntoSections(rawText) {
  if (!rawText) return []

  // Build a regex that matches any of the headers, case‑insensitive,
  // optionally followed by dashes. We'll capture the matched header.
  const escapedHeaders = SECTION_HEADERS.map(h => escapeRegExp(h)).join('|')
  const headerRegex = new RegExp(`\\b(${escapedHeaders})[ \\-]*`, 'gi')

  const sections = []
  let lastIndex = 0
  let match

  while ((match = headerRegex.exec(rawText)) !== null) {
    const header = match[1].toUpperCase()  // normalise to uppercase for consistent display
    const start = match.index
    // Capture everything before this match as the body of the previous section
    if (sections.length > 0) {
      sections[sections.length - 1].body = rawText.slice(lastIndex, start).trim()
    }
    // Start a new section
    sections.push({ header: toTitleCase(header), body: '' })
    lastIndex = match.index + match[0].length
  }
  // Capture the body of the last section
  if (sections.length > 0) {
    sections[sections.length - 1].body = rawText.slice(lastIndex).trim()
  }

  // If no sections found, fall back to plain text
  if (sections.length === 0) {
    return [{ header: null, body: rawText.trim() }]
  }

  return sections
}

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function toTitleCase(str) {
  return str.replace(/\w\S*/g, txt => txt.charAt(0).toUpperCase() + txt.slice(1).toLowerCase())
}

function formatMessage(text) {
  if (!text) return null
  const sections = splitIntoSections(text)

  if (sections.length === 1 && !sections[0].header) {
    // Only one plain text block – render as is
    return <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{sections[0].body}</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {sections.map((sec, i) => (
        <div key={i} className="glass" style={{ padding: '1rem', border: '1px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--bg-card)' }}>
          {sec.header && (
            <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.75rem', color: 'var(--accent)', borderBottom: '1px solid var(--border)', paddingBottom: '0.4rem' }}>
              {sec.header}
            </div>
          )}
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
            {sec.body}
          </div>
        </div>
      ))}
    </div>
  )
}

/* =====================================================
   Chat component
   ===================================================== */
export default function Chat() {
  const { token, logout } = useAuth()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [toolCalls, setToolCalls] = useState([])
  const [loading, setLoading] = useState(false)
  const eventSourceRef = useRef(null)
  const chatEndRef = useRef(null)

  const handleSend = () => {
    if (!query.trim()) return
    setLoading(true)
    setToolCalls([])
    setMessages([])

    if (eventSourceRef.current) eventSourceRef.current.close()

    eventSourceRef.current = streamTripPlan(
      token,
      query,
      (event) => {
        if (event.type === 'token') {
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last && last.role === 'assistant') {
              return [...prev.slice(0, -1), { ...last, content: last.content + event.content }]
            }
            return [...prev, { role: 'assistant', content: event.content }]
          })
        } else if (event.type === 'tool_call') {
          setToolCalls(prev => [...prev, { tool: event.tool, input: event.input, status: 'running' }])
        } else if (event.type === 'tool_result') {
          setToolCalls(prev =>
            prev.map(tc => tc.tool === event.tool ? { ...tc, output: event.output, status: event.status || 'success' } : tc)
          )
        } else if (event.type === 'final_answer') {
          setMessages(prev => [...prev, { role: 'assistant', content: event.content, final: true }])
        }
      },
      () => setLoading(false),
      (err) => {
        console.error('Stream error', err)
        setLoading(false)
      }
    )
  }

  const handleLogout = () => {
    if (eventSourceRef.current) eventSourceRef.current.close()
    logout()
    navigate('/login')
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    return () => { if (eventSourceRef.current) eventSourceRef.current.close() }
  }, [])

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{ padding: '1rem 0', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)', position: 'sticky', top: 0, zIndex: 10 }}>
        <div className="container flex-between">
          <h1 style={{ fontSize: 'clamp(1.2rem, 3vw, 1.8rem)', fontWeight: 600, background: 'linear-gradient(135deg, #6c63ff, #42a5f5)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            ✈️ Smart Travel Planner
          </h1>
          <button onClick={handleLogout} style={{ background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-secondary)', padding: '0.5rem 1rem' }}>Log out</button>
        </div>
      </header>

      {/* Chat area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem 0' }}>
        <div className="container" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {messages.length === 0 && !loading && (
            <div style={{ textAlign: 'center', marginTop: '10vh', color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🌍</div>
              <h2 style={{ fontSize: 'clamp(1.2rem, 2.5vw, 1.8rem)', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Plan your perfect trip</h2>
              <p>Describe your dream vacation and I'll find the best options using real data.</p>
            </div>
          )}

          <ToolCallList calls={toolCalls} />

          {messages.map((msg, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div className="glass message-bubble" style={{ background: msg.role === 'user' ? 'linear-gradient(135deg, var(--accent), #42a5f5)' : 'var(--bg-card)', border: msg.role === 'user' ? 'none' : '1px solid var(--border)' }}>
                <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem', color: msg.role === 'user' ? 'rgba(255,255,255,0.8)' : 'var(--text-secondary)' }}>
                  {msg.role === 'user' ? 'You' : msg.final ? '✨ Final plan' : 'Assistant'}
                </div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                  {formatMessage(msg.content)}
                </div>
              </div>
            </div>
          ))}
          {loading && messages.length === 0 && (
            <div style={{ textAlign: 'center', marginTop: '2rem' }}>
              <div className="glass" style={{ display: 'inline-block', padding: '0.75rem 1.5rem' }}>
                <span style={{ marginRight: '0.5rem' }}>⏳</span> Agent is working…
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input bar */}
      <div style={{ padding: '1rem 0', borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)', position: 'sticky', bottom: 0 }}>
        <div className="container flex-between" style={{ gap: '0.75rem' }}>
          <input
            type="text"
            placeholder="Describe your trip... (e.g., Two weeks in July, warm, hiking, under $1500)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            style={{ flex: 1, minWidth: 0 }}
          />
          <button onClick={handleSend} disabled={loading} style={{ height: '3rem' }}>Send</button>
        </div>
      </div>
    </div>
  )
}