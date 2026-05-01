// frontend/src/components/Chat.jsx
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { streamTripPlan } from '../services/api'
import ToolCallList from './ToolCallList'
import '../styles/global.css'

/* ================================================================
   Modern, dynamic section renderer (final version)
   ================================================================ */

/** Keys the model might output as plain text */
const SECTION_KEYS = [
    'recommended_destination',
    'current_weather',
    'itinerary',
    'budget_breakdown',
    'caveats',
]

/** Icons for each card */
const ICONS = {
    'Recommended Destination': '🏙️',
    'Current Weather': '🌤️',
    '2-Week Itinerary': '🗓️',
    'Budget Breakdown': '💰',
    'Important Caveats': '⚠️',
}

/**
 * Insert two newlines before every known section key.
 * This ensures blank lines between sections for reliable splitting.
 */
function preprocessText(raw) {
    let text = raw
    for (const key of SECTION_KEYS) {
        const regex = new RegExp(`(${key})`, 'g')
        text = text.replace(regex, '\n\n$1')
    }
    return text.replace(/\n{3,}/g, '\n\n').trim()
}


function cleanBody(title, rawBody) {
    if (!rawBody) return rawBody

    // Define sub‑keys for each section (in order of appearance)
    const subKeys = {
        'Recommended Destination': ['name', 'why'],
        'Current Weather': ['description', 'packing_advice'],
        '2-Week Itinerary': null,            // itinerary is just a list – keep as is
        'Budget Breakdown': ['flights', 'accommodation', 'activities', 'food_transport', 'total'],
        'Important Caveats': null,           // caveats is a free‑text block
    }

    const keysForSection = subKeys[title]
    if (!keysForSection) return rawBody   // no special cleaning needed

    let body = rawBody
    const parts = []
    let remaining = body

    // Try to split on each known sub‑key, preserving the key as a label
    for (const key of keysForSection) {
        const idx = remaining.indexOf(key)
        if (idx !== -1) {
            // Everything before this key is part of the previous value (should be empty)
            if (idx > 0) {
                // If there is text before, attach it to the previous part (or as plain text)
                const before = remaining.substring(0, idx).trim()
                if (before) parts.push(before)
            }
            // Remove the key and collect the value until the next known sub‑key or end
            remaining = remaining.substring(idx + key.length)
            // Find the next sub‑key to know where this value ends
            let nextIdx = remaining.length
            for (const nextKey of keysForSection) {
                const pos = remaining.indexOf(nextKey)
                if (pos !== -1 && pos < nextIdx) nextIdx = pos
            }

           let value = remaining.substring(0, nextIdx).trim()

            // For budget breakdown, ensure a dollar sign and keep the tilde if present
            if (title === 'Budget Breakdown' && value) {
                value = value.replace(/^[^\d~]+/, '')   // remove any non‑numeric / non‑tilde prefix
                if (!value.startsWith('~') && !value.startsWith('$')) {
                    value = '$' + value
                } else if (value.startsWith('~') && !value.startsWith('~$')) {
                    value = '~$' + value.substring(1)
                }
            }
            // Format as "Key: Value"
            const label = key.replace(/_/g, ' ')
                             .replace(/\b\w/g, c => c.toUpperCase())
            parts.push(`${label}: ${value}`)
            remaining = remaining.substring(nextIdx)
        }
    }
    // If any leftover text, add it as a note
    if (remaining.trim()) parts.push(remaining.trim())

    return parts.join('\n') || rawBody
}

/**
 * Attempt to parse JSON; if that fails, pre‑process the text
 * and split it into sections. Each section has a title and
 * a cleaned body (the key prefix is removed).
 */
function extractSections(text) {
    if (!text) return []

    // 1) Try to parse as JSON
    let trip = null
    try {
        const cleaned = text.replace(/```json|```/g, '').trim()
        trip = JSON.parse(cleaned)
    } catch { /* not JSON */ }

    if (trip && typeof trip === 'object') {
        const sections = []
        if (trip.recommended_destination) {
            sections.push({
                title: 'Recommended Destination',
                body: `Name: ${trip.recommended_destination.name}\n\n${trip.recommended_destination.why}`,
            })
        }
        if (trip.current_weather) {
            sections.push({
                title: 'Current Weather',
                body: `${trip.current_weather.description}\n\nPacking: ${trip.current_weather.packing_advice}`,
            })
        }
        if (trip.itinerary && Array.isArray(trip.itinerary)) {
            sections.push({
                title: '2-Week Itinerary',
                body: trip.itinerary.map((day, i) => `Day ${i + 1}: ${day}`).join('\n'),
            })
        }
        if (trip.budget_breakdown) {
            sections.push({
                title: 'Budget Breakdown',
                body: [
                    `Flights: ${trip.budget_breakdown.flights}`,
                    `Accommodation: ${trip.budget_breakdown.accommodation}`,
                    `Activities: ${trip.budget_breakdown.activities}`,
                    `Food & Transport: ${trip.budget_breakdown.food_transport}`,
                    `Total: ${trip.budget_breakdown.total}`,
                ].join('\n'),
            })
        }
        if (trip.caveats) {
            sections.push({ title: 'Important Caveats', body: trip.caveats })
        }
        if (sections.length) return sections
    }

    // 2) Pre‑process the raw text
    const preprocessed = preprocessText(text)

    // 3) Split on blank lines
    const blocks = preprocessed.split(/\n\s*\n/).filter(b => b.trim())

    // 4) Process each block – extract key, assign title, and clean the body
    return blocks.map(block => {
        let title = ''
        let body = block.trim()
        for (const key of SECTION_KEYS) {
            if (body.startsWith(key)) {
                if (key === 'recommended_destination') title = 'Recommended Destination'
                else if (key === 'current_weather') title = 'Current Weather'
                else if (key === 'itinerary') title = '2-Week Itinerary'
                else if (key === 'budget_breakdown') title = 'Budget Breakdown'
                else if (key === 'caveats') title = 'Important Caveats'
                body = body.substring(key.length).trim()
                break
            }
        }
        // If no key found, keep original
        if (!title) {
            title = ''
            body = block.trim()
        }
        // Clean the body (split sub‑keys, etc.)
        body = cleanBody(title, body)
        return { title, body }
    })
}

/* ===== Main renderer ===== */
function formatMessage(text) {
    if (!text) return null
    const sections = extractSections(text)

    // Single section with no title → plain text
    if (sections.length === 1 && !sections[0].title) {
        return <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{sections[0].body}</div>
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {sections.map((sec, i) => (
                <div
                    key={i}
                    className="glass"
                    style={{
                        padding: '1.25rem',
                        borderRadius: 'var(--radius)',
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border)',
                    }}
                >
                    {sec.title && (
                        <h3
                            style={{
                                margin: '0 0 0.75rem 0',
                                fontSize: '1rem',
                                fontWeight: 600,
                                color: 'var(--accent)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                borderBottom: '1px solid var(--border)',
                                paddingBottom: '0.5rem',
                            }}
                        >
                            <span style={{ fontSize: '1.3rem' }}>
                                {ICONS[sec.title] || '📌'}
                            </span>
                            {sec.title}
                        </h3>
                    )}
                    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                        {sec.body}
                    </div>
                </div>
            ))}
        </div>
    )
}

/* ================================================================
   Chat component (unchanged)
   ================================================================ */
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

    useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
    useEffect(() => { return () => { if (eventSourceRef.current) eventSourceRef.current.close() } }, [])

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