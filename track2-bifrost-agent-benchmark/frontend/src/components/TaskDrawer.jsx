import { AlertTriangle, ArrowRight, CheckCircle2, FileText, Shield, Wrench } from 'lucide-react'
import { Drawer } from './Dialog.jsx'

const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard' }

export default function TaskDrawer({ open, task, category, onClose }) {
  if (!task) return null
  return (
    <Drawer
      open={open}
      onClose={onClose}
      eyebrow={`Task ${String(task.number).padStart(2, '0')} · ${category?.name || task.category}`}
      title={task.title}
      subtitle={task.prompt}
    >
      <div className="task-meta-row">
        <span className={`difficulty difficulty-${task.difficulty}`}>{DIFFICULTY_LABEL[task.difficulty] || task.difficulty}</span>
        <span className="meta-chip"><Shield size={13} /> {task.risk} risk</span>
        <span className="meta-chip"><CheckCircle2 size={13} /> {task.checks.length} checks</span>
        <span className="meta-chip"><Wrench size={13} /> {task.tools.length} tools</span>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Customer message</h3></div>
        <blockquote className="customer-quote">“{task.prompt}”</blockquote>
        <div className="context-block">
          <span className="mono-label">Context</span>
          <p>{task.context}</p>
        </div>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Policy</h3><FileText size={15} className="section-icon" /></div>
        <p className="body-copy">{task.policy}</p>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Deterministic checks</h3><span className="mono-label">weighted</span></div>
        <div className="check-list">
          {task.checks.map((check, index) => (
            <div className="check-row" key={check.id}>
              <span className="check-index">{String(index + 1).padStart(2, '0')}</span>
              <span className="check-copy">{check.label}</span>
              <span className={`check-kind kind-${check.kind}`}>{check.kind}</span>
              <span className="check-weight">×{check.weight}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="drawer-section">
        <div className="drawer-section-head"><h3>Tools available</h3></div>
        <div className="tool-list">
          {task.tools.map((tool) => <code key={tool}>{tool}</code>)}
        </div>
      </div>

      <div className="drawer-section two-up">
        <div className="answer-card answer-good">
          <span className="answer-label"><CheckCircle2 size={14} /> What good looks like</span>
          <p>{task.resolution}</p>
        </div>
        <div className="answer-card answer-bad">
          <span className="answer-label"><AlertTriangle size={14} /> Common trap</span>
          <p>{task.trap}</p>
        </div>
      </div>

      <div className="drawer-note">
        <ArrowRight size={14} />
        <span>Every agent gets this exact task, context and policy. Scores come from the checks, not from the answer's confidence.</span>
      </div>
    </Drawer>
  )
}
