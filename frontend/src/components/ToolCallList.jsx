export default function ToolCallList({ calls }) {
  if (!calls || calls.length === 0) return null

  return (
    <div>
      <h4 style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem', textTransform: 'uppercase', fontSize: '0.85rem', letterSpacing: '1px' }}>🔧 Tool Calls</h4>
      {calls.map((call, i) => (
        <div key={i} className="glass" style={{ padding: '0.75rem 1rem', marginBottom: '0.5rem', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', borderLeft: `4px solid ${call.status === 'error' ? 'var(--danger)' : 'var(--accent)'}` }}>
          <div style={{ flex: 1 }}>
            <strong style={{ color: call.status === 'error' ? 'var(--danger)' : 'var(--accent)' }}>{call.tool}</strong>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              {call.status === 'running' ? '⏳ Running...' : call.status === 'error' ? '❌ Failed' : '✅ Completed'}
            </div>
          </div>
          <details>
            <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)', fontWeight: 500 }}>Details</summary>
            <pre>{JSON.stringify(call, null, 2)}</pre>
          </details>
        </div>
      ))}
    </div>
  )
}