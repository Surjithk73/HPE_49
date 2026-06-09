import React from 'react'
import { Link } from 'react-router-dom'
import { Database, Cpu, Search, Sparkles, Zap, Shield, ArrowRight, BarChart3, MessageSquare } from 'lucide-react'

export default function Landing() {
  return (
    <div style={{ minHeight: '100vh', background: '#0a0a0a', color: '#f0f0f0', fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace' }}>
      {/* Navbar */}
      <header style={{ borderBottom: '1px solid #1c1c1c', background: 'rgba(17,17,17,0.8)', backdropFilter: 'blur(12px)', position: 'sticky', top: 0, zIndex: 100 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '64px' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Cpu size={15} style={{ color: '#3b82f6' }} />
            </div>
            <div>
              <div style={{ fontSize: '15px', fontWeight: 700, color: '#f0f0f0', letterSpacing: '-0.02em' }}>QueryCraft</div>
            </div>
          </Link>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <Link to="/how-it-works" style={{ color: '#aaa', fontSize: '13px', textDecoration: 'none', fontWeight: 500, transition: 'color 0.2s' }} onMouseEnter={e => e.currentTarget.style.color = '#fff'} onMouseLeave={e => e.currentTarget.style.color = '#aaa'}>
              How it Works
            </Link>
            <Link to="/dashboard" style={{ padding: '8px 16px', borderRadius: '8px', background: '#3b82f6', color: '#fff', fontSize: '13px', textDecoration: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', transition: 'background 0.2s' }} onMouseEnter={e => e.currentTarget.style.background = '#2563eb'} onMouseLeave={e => e.currentTarget.style.background = '#3b82f6'}>
              Launch Dashboard <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main>
        <section style={{ padding: '120px 24px', textAlign: 'center', background: 'radial-gradient(circle at 50% 0%, rgba(59,130,246,0.1) 0%, transparent 50%)' }}>
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            <h1 style={{ fontSize: '56px', fontWeight: 800, margin: '0 0 24px', letterSpacing: '-0.03em', lineHeight: 1.1, background: 'linear-gradient(180deg, #ffffff 0%, #a0a0a0 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Talk to your <br /> HPE NonStop data.
            </h1>
            
            <p style={{ fontSize: '18px', color: '#888', lineHeight: 1.6, marginBottom: '48px', maxWidth: '600px', marginInline: 'auto' }}>
              Transform complex natural language questions into highly optimized PostgreSQL queries instantly. The smartest way to analyze system performance metrics.
            </p>
            
            <div style={{ display: 'flex', gap: '16px', justifyContent: 'center' }}>
              <Link to="/dashboard" style={{ padding: '14px 28px', borderRadius: '12px', background: '#3b82f6', color: '#fff', fontSize: '15px', textDecoration: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', transition: 'transform 0.2s, background 0.2s' }} onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.background = '#2563eb' }} onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.background = '#3b82f6' }}>
                Try the System
              </Link>
              <Link to="/how-it-works" style={{ padding: '14px 28px', borderRadius: '12px', background: '#161616', border: '1px solid #333', color: '#f0f0f0', fontSize: '15px', textDecoration: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', transition: 'background 0.2s' }} onMouseEnter={e => e.currentTarget.style.background = '#222'} onMouseLeave={e => e.currentTarget.style.background = '#161616'}>
                View Architecture
              </Link>
            </div>
          </div>
        </section>

        {/* Value Props */}
        <section style={{ padding: '80px 24px', borderTop: '1px solid #1c1c1c', background: '#0a0a0a' }}>
          <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
            <div style={{ textAlign: 'center', marginBottom: '64px' }}>
              <h2 style={{ fontSize: '32px', fontWeight: 700, margin: '0 0 16px', letterSpacing: '-0.02em' }}>Built for scale. Designed for humans.</h2>
              <p style={{ color: '#888', fontSize: '16px' }}>QueryCraft bypasses the need for manual SQL composition, giving you immediate insights.</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
              {[
                { icon: MessageSquare, color: '#3b82f6', title: 'Natural Language to SQL', desc: 'Ask questions in plain English. Our fine-tuned Gemini model generates complex JOINs and aggregations automatically.' },
                { icon: Zap, color: '#f59e0b', title: 'Semantic Caching', desc: 'ChromaDB instantly serves previously answered queries with 95% semantic similarity, reducing latency from seconds to milliseconds.' },
                { icon: Shield, color: '#10b981', title: 'Secure & Validated', desc: 'Built-in SQLGlot AST parsing ensures 100% read-only queries. Zero chance of SQL injection or accidental database modification.' },
                { icon: Database, color: '#8b5cf6', title: 'Multi-Node Management', desc: 'Dynamically append and manage Measure CSV data across multiple virtual HPE NonStop nodes effortlessly.' },
                { icon: BarChart3, color: '#ec4899', title: 'Instant Visualization', desc: 'QueryCraft auto-detects time-series and categorical data to generate beautiful charts immediately after execution.' },
                { icon: Search, color: '#06b6d4', title: 'Smart Schema Linking', desc: 'Our semantic router precisely identifies the correct tables and columns out of 600+ possibilities before generating SQL.' }
              ].map((feature, i) => (
                <div key={i} style={{ padding: '32px', background: '#111', border: '1px solid #1c1c1c', borderRadius: '16px' }}>
                  <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: `${feature.color}15`, border: `1px solid ${feature.color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '24px' }}>
                    <feature.icon size={24} color={feature.color} />
                  </div>
                  <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#f0f0f0', margin: '0 0 12px' }}>{feature.title}</h3>
                  <p style={{ fontSize: '14px', color: '#888', lineHeight: 1.6, margin: 0 }}>{feature.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid #1c1c1c', background: '#0a0a0a', padding: '40px 24px', textAlign: 'center' }}>
        <p style={{ fontSize: '13px', color: '#666', margin: 0 }}>
          QueryCraft © 2026. HPE NonStop Performance Analytics.
        </p>
      </footer>
    </div>
  )
}
