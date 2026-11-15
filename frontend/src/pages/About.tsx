import { Info, Shield, Database, GitBranch, ExternalLink } from 'lucide-react'
import Panel from '../components/Panel'
import { Divider, SectionLabel } from '../components/ui'

const ROADMAP = [
  { milestone: 1,  title: 'Repository Inspection',            status: 'done',    desc: 'Project structure established, greenfield confirmed.' },
  { milestone: 2,  title: 'Application Shell & UI',           status: 'done',    desc: 'All pages, navigation, design system, demo data.' },
  { milestone: 3,  title: 'Explorer & Metadata Integration',  status: 'done',    desc: 'IRSA archive search and confirmed observation metadata.' },
  { milestone: 4,  title: 'FastAPI Service & FITS Endpoints', status: 'done',    desc: 'FITS inspection, WCS coordinates, and source APIs.' },
  { milestone: 5,  title: 'Scientific Image Viewer',          status: 'done',    desc: 'FITS preview, image statistics, and inspection.' },
  { milestone: 6,  title: 'Time Machine Comparison',          status: 'partial', desc: 'One real epoch is available; a compatible second epoch is not confirmed.' },
  { milestone: 7,  title: 'Discovery Lab Measurements',       status: 'done',    desc: 'Source detection and aperture photometry with scientific limitations.' },
  { milestone: 8,  title: 'Evidence Capsule Generation',      status: 'partial', desc: 'Static example capsule only; live analysis is not persisted into capsules.' },
  { milestone: 9,  title: 'Supabase Integration',             status: 'planned', desc: 'Database, storage, authentication, persistence.' },
  { milestone: 10, title: 'Testing & Deployment',             status: 'partial', desc: 'Regression-tested prototype; public hosting awaits repository and account authorization.' },
]

const statusColor: Record<string, string> = {
  done: '#4ade80', partial: '#fbbf24', planned: '#4a6080',
}

const PRINCIPLES = [
  {
    icon: Shield,
    title: 'Scientific Integrity',
    points: [
      'Original FITS data is never silently modified.',
      'WCS metadata and coordinate conventions are preserved.',
      'Units are documented throughout.',
      'Uncertainty is not reported until its data semantics are verified.',
      'Missing data is distinguished from zero-valued data.',
      'ZODI subtraction not applied without verified scientific justification.',
    ],
  },
  {
    icon: Database,
    title: 'Data Honesty',
    points: [
      'Demo data is always clearly labelled.',
      'No fabricated observations are stored as real data.',
      'Multi-epoch comparison not claimed until two compatible observations confirmed.',
      'Calibration applicability is not assumed.',
      'Observation IDs and FITS provenance are shown when available.',
    ],
  },
  {
    icon: GitBranch,
    title: 'Reproducibility',
    points: [
      'The example Evidence Capsule is static and clearly labelled.',
      'Processing metadata is recorded by analysis; live capsule integration is unfinished.',
      'Candidates are never automatically confirmed as discoveries.',
      'Human review is required for every candidate classification.',
      'Scientific limitations are documented in every capsule.',
    ],
  },
]

export default function About() {
  return (
    <div style={{ paddingTop: 56, minHeight: '100vh' }}>
      <div style={{
        borderBottom: '1px solid rgba(34, 211, 238, 0.1)',
        padding: '28px 24px 20px',
        background: 'rgba(6, 13, 24, 0.4)',
      }}>
        <div className="page-container">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
            <Info size={20} color="#22d3ee" />
            <h1 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: '#f0f4f8' }}>About COSMIC PULSE</h1>
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#8899aa', maxWidth: 600 }}>
            Mission, methodology, scientific principles, and development roadmap.
          </p>
        </div>
      </div>

      <div className="page-container" style={{ padding: '40px 24px', maxWidth: 900 }}>

        {/* Mission */}
        <div style={{ marginBottom: 48 }}>
          <SectionLabel>Mission</SectionLabel>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f0f4f8', margin: '8px 0 16px', lineHeight: 1.2 }}>
            Transforming observations into<br />
            <span className="text-gradient-cyan">reproducible investigations</span>
          </h2>
          <p style={{ fontSize: '0.95rem', color: '#8899aa', lineHeight: 1.8, maxWidth: 680, margin: 0 }}>
            COSMIC PULSE is an astronomical investigation platform built for the NASA Space Apps Challenge 2026,
            aligned with Challenge 12: Planet X and SPHEREx. It transforms genuine SPHEREx mission observations
            into interactive, explainable, and reproducible investigations — helping users navigate real data,
            investigate possible changes, understand scientific evidence, and share verifiable results.
          </p>
        </div>

        <Divider />

        {/* SPHEREx alignment */}
        <div style={{ margin: '40px 0' }}>
          <SectionLabel>SPHEREx Alignment</SectionLabel>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f0f4f8', margin: '8px 0 16px' }}>
            Built on real mission data
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
            {[
              { label: 'Mission', value: 'SPHEREx — Spectro-Photometer for the History of the Universe, Epoch of Reionization, and Ices Explorer' },
              { label: 'Data Release', value: 'DR1 Level-2' },
              { label: 'Observation ID', value: '2025W17_4B_0001_1' },
              { label: 'Observation Date', value: '24 April 2025' },
              { label: 'Detector', value: 'D1' },
              { label: 'Challenge', value: 'NASA Space Apps 2026 — Challenge 12: Planet X and SPHEREx' },
            ].map(({ label, value }) => (
              <div key={label} style={{
                padding: '14px 16px', borderRadius: 7,
                background: 'rgba(34, 211, 238, 0.03)',
                border: '1px solid rgba(34, 211, 238, 0.1)',
              }}>
                <div style={{ fontSize: '0.65rem', color: '#8899aa', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 5 }}>{label}</div>
                <div style={{ fontSize: '0.82rem', color: '#f0f4f8', lineHeight: 1.4 }}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        <Divider />

        {/* Principles */}
        <div style={{ margin: '40px 0' }}>
          <SectionLabel>Scientific Principles</SectionLabel>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f0f4f8', margin: '8px 0 24px' }}>
            How we handle data
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
            {PRINCIPLES.map(({ icon: Icon, title, points }) => (
              <Panel key={title}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 8,
                    background: 'rgba(34, 211, 238, 0.08)',
                    border: '1px solid rgba(34, 211, 238, 0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Icon size={16} color="#22d3ee" />
                  </div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f0f4f8' }}>{title}</div>
                </div>
                <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {points.map((p, i) => (
                    <li key={i} style={{ display: 'flex', gap: 7, fontSize: '0.78rem', color: '#8899aa', lineHeight: 1.5 }}>
                      <span style={{ color: '#22d3ee', flexShrink: 0 }}>·</span> {p}
                    </li>
                  ))}
                </ul>
              </Panel>
            ))}
          </div>
        </div>

        <Divider />

        {/* Roadmap */}
        <div style={{ margin: '40px 0' }}>
          <SectionLabel>Development Roadmap</SectionLabel>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f0f4f8', margin: '8px 0 24px' }}>
            Prototype status
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {ROADMAP.map(({ milestone, title, status, desc }) => (
              <div key={milestone} style={{
                display: 'flex', gap: 14, alignItems: 'flex-start',
                padding: '12px 16px', borderRadius: 7,
                background: status === 'done' ? 'rgba(74, 222, 128, 0.04)' : status === 'partial' ? 'rgba(251, 191, 36, 0.04)' : 'rgba(6, 13, 24, 0.4)',
                border: `1px solid ${status === 'done' ? 'rgba(74, 222, 128, 0.15)' : status === 'partial' ? 'rgba(251, 191, 36, 0.15)' : 'rgba(34, 211, 238, 0.06)'}`,
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: `${statusColor[status]}18`,
                  border: `1px solid ${statusColor[status]}40`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.65rem', fontWeight: 700, color: statusColor[status],
                }}>
                  {milestone}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: status === 'planned' ? '#8899aa' : '#f0f4f8' }}>{title}</span>
                    <span style={{
                      fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.08em',
                      padding: '2px 6px', borderRadius: 3,
                      background: `${statusColor[status]}18`,
                      color: statusColor[status],
                      border: `1px solid ${statusColor[status]}30`,
                    }}>
                      {status === 'done' ? 'COMPLETE' : status === 'partial' ? 'PARTIAL' : 'PLANNED'}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#8899aa' }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <Divider />

        {/* External links */}
        <div style={{ margin: '40px 0' }}>
          <SectionLabel>Resources</SectionLabel>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 12 }}>
            {[
              { label: 'NASA Space Apps Challenge', url: 'https://www.spaceappschallenge.org' },
              { label: 'SPHEREx Mission', url: 'https://spherex.caltech.edu' },
              { label: 'SPHEREx DR1 Archive (IRSA)', url: 'https://irsa.ipac.caltech.edu/Missions/spherex.html' },
            ].map(({ label, url }) => (
              <a key={label} href={url} target="_blank" rel="noopener noreferrer" className="btn-ghost" style={{ fontSize: '0.8rem' }}>
                {label} <ExternalLink size={11} />
              </a>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}
