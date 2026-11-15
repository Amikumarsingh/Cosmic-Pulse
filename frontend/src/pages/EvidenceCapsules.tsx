import { useState } from 'react'
import { Archive, Download, Copy, CheckCircle, Clock, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'
import Panel from '../components/Panel'
import { MetaRow, Badge, LimitationList, SectionLabel, Divider } from '../components/ui'
import { DEMO_EVIDENCE_CAPSULE } from '../data/demoData'
import type { CandidateStatus } from '../types'

const STATUS_CONFIG: Record<CandidateStatus, { label: string; color: string; icon: typeof CheckCircle }> = {
  selected:               { label: 'Selected',              color: '#8899aa', icon: Clock },
  observations_retrieved: { label: 'Observations Retrieved', color: '#22d3ee', icon: Clock },
  analysis_completed:     { label: 'Analysis Completed',    color: '#67e8f9', icon: Clock },
  flagged:                { label: 'Candidate Flagged',     color: '#fbbf24', icon: AlertTriangle },
  human_review:           { label: 'Human Review',          color: '#a78bfa', icon: Clock },
  confirmed:              { label: 'Confirmed',             color: '#4ade80', icon: CheckCircle },
  rejected:               { label: 'Rejected',              color: '#f87171', icon: AlertTriangle },
  unresolved:             { label: 'Unresolved',            color: '#a78bfa', icon: AlertTriangle },
}

const LIFECYCLE_STEPS: CandidateStatus[] = [
  'selected', 'observations_retrieved', 'analysis_completed', 'flagged', 'human_review',
]

function CandidateLifecycle({ current }: { current: CandidateStatus }) {
  const currentIdx = LIFECYCLE_STEPS.indexOf(current)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap' }}>
      {LIFECYCLE_STEPS.map((step, i) => {
        const cfg = STATUS_CONFIG[step]
        const done = i <= currentIdx
        return (
          <div key={step} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              padding: '0 8px',
            }}>
              <div style={{
                width: 10, height: 10, borderRadius: '50%',
                background: done ? cfg.color : 'rgba(136, 153, 170, 0.2)',
                border: `2px solid ${done ? cfg.color : 'rgba(136, 153, 170, 0.3)'}`,
                boxShadow: done ? `0 0 6px ${cfg.color}` : 'none',
              }} />
              <div style={{ fontSize: '0.58rem', color: done ? cfg.color : '#4a6080', textAlign: 'center', maxWidth: 60, lineHeight: 1.3 }}>
                {cfg.label}
              </div>
            </div>
            {i < LIFECYCLE_STEPS.length - 1 && (
              <div style={{ width: 16, height: 1, background: i < currentIdx ? 'rgba(34, 211, 238, 0.3)' : 'rgba(136, 153, 170, 0.15)', flexShrink: 0 }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function EvidenceCapsules() {
  const capsule = DEMO_EVIDENCE_CAPSULE
  const [expandedStep, setExpandedStep] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)

  function copyId() {
    navigator.clipboard.writeText(capsule.id).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(capsule, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `evidence-capsule-${capsule.id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const statusCfg = STATUS_CONFIG[capsule.candidateStatus]
  const StatusIcon = statusCfg.icon

  return (
    <div style={{ paddingTop: 56, minHeight: '100vh' }}>
      {/* Page header */}
      <div style={{
        borderBottom: '1px solid rgba(196, 181, 253, 0.15)',
        padding: '28px 24px 20px',
        background: 'rgba(6, 13, 24, 0.4)',
      }}>
        <div className="page-container">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
            <Archive size={20} color="#c4b5fd" />
            <h1 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: '#f0f4f8' }}>Evidence Capsules</h1>
            <Badge variant="demo" />
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#8899aa', maxWidth: 600 }}>
            Prototype preview of an example capsule. Exported content is static demo data and is not generated from Discovery Lab analysis.
          </p>
        </div>
      </div>

      <div className="page-container" style={{ padding: '24px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, alignItems: 'start' }}>

          {/* Left: Capsule detail */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Header card */}
            <Panel>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#22d3ee' }}>{capsule.id}</div>
                    <button onClick={copyId} className="btn-ghost" style={{ padding: '2px 6px' }}>
                      {copied ? <CheckCircle size={11} color="#4ade80" /> : <Copy size={11} />}
                    </button>
                  </div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f0f4f8', marginBottom: 4 }}>
                    SPHEREx DR1 Initial Inspection
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#8899aa' }}>
                    Created {new Date(capsule.createdAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Badge variant="demo" />
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '4px 10px', borderRadius: 4,
                    background: `${statusCfg.color}18`,
                    border: `1px solid ${statusCfg.color}30`,
                    fontSize: '0.7rem', fontWeight: 600, color: statusCfg.color,
                  }}>
                    <StatusIcon size={11} />
                    {statusCfg.label.toUpperCase()}
                  </div>
                </div>
              </div>

              <Divider />

              <div style={{ marginBottom: 12 }}>
                <SectionLabel>Candidate Lifecycle</SectionLabel>
                <div style={{ marginTop: 12 }}>
                  <CandidateLifecycle current={capsule.candidateStatus} />
                </div>
              </div>

              <div style={{ padding: '10px 12px', background: 'rgba(167, 139, 250, 0.05)', border: '1px solid rgba(167, 139, 250, 0.15)', borderRadius: 5 }}>
                <div style={{ fontSize: '0.72rem', color: '#a78bfa', display: 'flex', gap: 6 }}>
                  <Clock size={12} style={{ flexShrink: 0, marginTop: 1 }} />
                  Awaiting human review. No candidate has been confirmed or rejected. Automatic discovery classification is never performed.
                </div>
              </div>
            </Panel>

            {/* Target & observations */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Panel title="Target Coordinates">
                <MetaRow label="RA (J2000)" value="Not yet confirmed" />
                <MetaRow label="Dec (J2000)" value="Not yet confirmed" />
                <MetaRow label="Mission" value={capsule.mission} />
                <MetaRow label="Human review" value={capsule.humanReviewStatus.toUpperCase()} />
              </Panel>

              <Panel title="Observations">
                {capsule.observationIds.map(id => (
                  <div key={id} style={{
                    padding: '8px 10px', borderRadius: 5, marginBottom: 6,
                    background: 'rgba(34, 211, 238, 0.04)',
                    border: '1px solid rgba(34, 211, 238, 0.1)',
                    fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#22d3ee',
                  }}>
                    {id}
                  </div>
                ))}
                <MetaRow label="Epochs" value={capsule.epochs.length.toString()} />
                <MetaRow label="FITS refs" value={capsule.fitsProductRefs.length.toString()} />
              </Panel>
            </div>

            {/* Processing steps */}
            <Panel title="Processing Steps">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {capsule.processingSteps.map(step => (
                  <div key={step.step} style={{
                    border: '1px solid rgba(34, 211, 238, 0.1)',
                    borderRadius: 6, overflow: 'hidden',
                  }}>
                    <button
                      onClick={() => setExpandedStep(expandedStep === step.step ? null : step.step)}
                      style={{
                        width: '100%', padding: '10px 14px',
                        background: 'rgba(6, 13, 24, 0.5)',
                        border: 'none', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: 10,
                        textAlign: 'left',
                      }}
                    >
                      <div style={{
                        width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                        background: 'rgba(34, 211, 238, 0.1)',
                        border: '1px solid rgba(34, 211, 238, 0.2)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.65rem', fontWeight: 700, color: '#22d3ee',
                      }}>
                        {step.step}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#f0f4f8' }}>{step.name}</div>
                        <div style={{ fontSize: '0.7rem', color: '#8899aa' }}>{step.softwareVersion}</div>
                      </div>
                      {expandedStep === step.step ? <ChevronDown size={14} color="#8899aa" /> : <ChevronRight size={14} color="#8899aa" />}
                    </button>
                    {expandedStep === step.step && (
                      <div style={{ padding: '12px 14px', background: 'rgba(2, 4, 8, 0.4)', borderTop: '1px solid rgba(34, 211, 238, 0.08)' }}>
                        <div style={{ fontSize: '0.78rem', color: '#8899aa', marginBottom: 8 }}>{step.description}</div>
                        {Object.keys(step.parameters).length > 0 && (
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: '#4a6080', background: 'rgba(2, 4, 8, 0.5)', padding: '8px', borderRadius: 4 }}>
                            {JSON.stringify(step.parameters, null, 2)}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Panel>

            {/* Measurements */}
            <Panel title="Measurements">
              <div style={{ padding: '20px', textAlign: 'center', background: 'rgba(2, 4, 8, 0.3)', border: '1px dashed rgba(34, 211, 238, 0.1)', borderRadius: 6 }}>
                <div style={{ fontSize: '0.82rem', color: '#4a6080', marginBottom: 4 }}>No measurements recorded</div>
                <div style={{ fontSize: '0.72rem', color: '#4a6080' }}>
                  Measurements will be added in Milestone 7 when the scientific processing backend is connected.
                </div>
              </div>
            </Panel>

            {/* Scientific limitations */}
            <Panel title="Scientific Limitations">
              <LimitationList items={capsule.scientificLimitations} />
            </Panel>
          </div>

          {/* Right: Sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Export */}
            <Panel title="Export">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button onClick={exportJson} className="btn-primary" style={{ justifyContent: 'center' }}>
                  <Download size={14} /> Export JSON
                </button>
                <button className="btn-secondary" disabled style={{ justifyContent: 'center', opacity: 0.4, cursor: 'not-allowed' }}>
                  Export PDF (Milestone 8)
                </button>
                <button className="btn-secondary" disabled style={{ justifyContent: 'center', opacity: 0.4, cursor: 'not-allowed' }}>
                  Share Link (Milestone 9)
                </button>
              </div>
              <div style={{ marginTop: 12, fontSize: '0.72rem', color: '#4a6080', lineHeight: 1.6 }}>
                JSON export includes all processing steps, parameters, software versions, and scientific limitations.
              </div>
            </Panel>

            {/* Software versions */}
            <Panel title="Software Versions">
              {Object.entries(capsule.softwareVersions).map(([k, v]) => (
                <MetaRow key={k} label={k} value={v} mono />
              ))}
            </Panel>

            {/* FITS references */}
            <Panel title="FITS References">
              {capsule.fitsProductRefs.map(ref => (
                <div key={ref} style={{
                  padding: '7px 10px', borderRadius: 4, marginBottom: 6,
                  background: 'rgba(2, 4, 8, 0.4)',
                  border: '1px solid rgba(34, 211, 238, 0.08)',
                  fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: '#8899aa',
                  wordBreak: 'break-all',
                }}>
                  {ref}
                </div>
              ))}
              <div style={{ fontSize: '0.7rem', color: '#4a6080', marginTop: 4 }}>
                Local file path not yet confirmed.
              </div>
            </Panel>

            {/* Human review */}
            <Panel title="Human Review">
              <div style={{ marginBottom: 10 }}>
                <Badge variant="pending" label="REVIEW PENDING" />
              </div>
              <div style={{ fontSize: '0.78rem', color: '#8899aa', lineHeight: 1.6, marginBottom: 12 }}>
                Every candidate requires human review before any classification. Automatic discovery confirmation is never performed.
              </div>
              <textarea
                placeholder="Add review notes…"
                disabled
                style={{
                  width: '100%',
                  background: 'rgba(2, 4, 8, 0.4)',
                  border: '1px solid rgba(34, 211, 238, 0.1)',
                  borderRadius: 5, color: '#4a6080',
                  padding: '8px 10px', fontSize: '0.78rem',
                  resize: 'vertical', minHeight: 70,
                  fontFamily: 'var(--font-sans)', outline: 'none',
                  cursor: 'not-allowed',
                }}
              />
              <div style={{ marginTop: 8, fontSize: '0.7rem', color: '#4a6080' }}>
                Human review interface: Milestone 8
              </div>
            </Panel>
          </div>
        </div>
      </div>
    </div>
  )
}
