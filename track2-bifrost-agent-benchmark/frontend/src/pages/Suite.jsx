import { ArrowRight, CheckCircle2, ClipboardList, Play, Scale, Shield, Wrench } from 'lucide-react'
import { Eyebrow, ProgressBar, SectionHeading } from '../components/ui.jsx'
import { SCORE_WEIGHTS } from '../lib/constants.js'

const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard' }

export default function Suite({ suite, onOpenTask, onRun }) {
  const categories = suite?.categories || []
  const tasks = suite?.tasks || []
  const byCategory = Object.fromEntries(categories.map((category) => [
    category.id,
    tasks.filter((task) => task.category === category.id),
  ]))

  return (
    <div className="page suite-page">
      <header className="page-head">
        <div>
          <Eyebrow>Shared task suite</Eyebrow>
          <h1>Commerce support <em>v3</em></h1>
          <p className="page-lede">
            Eighteen tasks across the full support lifecycle. Every agent gets the same customer message, context and policy — and the same deterministic checks.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={onRun}>
          <Play size={15} /> Run suite
        </button>
      </header>

      <div className="suite-summary">
        <div><span className="mono-label">Tasks</span><strong>{suite?.task_count || 18}</strong><small>shared</small></div>
        <div><span className="mono-label">Categories</span><strong>{categories.length}</strong><small>lifecycle areas</small></div>
        <div><span className="mono-label">Scoring</span><strong>6</strong><small>dimensions</small></div>
        <div><span className="mono-label">Checks</span><strong>{tasks.reduce((sum, task) => sum + task.checks.length, 0)}</strong><small>deterministic</small></div>
      </div>

      <div className="suite-grid">
        <section className="panel scoring-panel">
          <SectionHeading title="How scoring works" meta="Composite score, weighted across six dimensions" />
          <div className="weight-list">
            {SCORE_WEIGHTS.map((item) => (
              <div className="weight-row" key={item.id}>
                <div className="weight-copy">
                  <span>{item.label}</span>
                  <small>{item.note}</small>
                </div>
                <ProgressBar value={item.weight * 2.5} tone="ink" height={5} />
                <span className="weight-value">{item.weight}%</span>
              </div>
            ))}
          </div>
          <div className="scoring-note">
            <Scale size={15} />
            <p>Task success is a pass/fail rate. Policy, tools, safety and consistency are weighted check pass rates. Efficiency is normalized against the other agents in the same run.</p>
          </div>
        </section>

        <section className="panel coverage-panel">
          <SectionHeading title="Coverage" meta="Four categories, one shared rubric" />
          <div className="suite-category-list">
            {categories.map((category) => {
              const count = byCategory[category.id]?.length || 0
              return (
                <div className="suite-category-row" key={category.id}>
                  <span className="category-dot" style={{ background: category.color }} />
                  <div>
                    <strong>{category.name}</strong>
                    <p>{category.description}</p>
                  </div>
                  <span className="mono-label">{count} tasks</span>
                </div>
              )
            })}
          </div>
        </section>
      </div>

      <div className="task-category-stack">
        {categories.map((category) => (
          <section className="panel task-category-panel" key={category.id}>
            <div className="category-head">
              <div className="category-head-copy">
                <span className="category-dot" style={{ background: category.color }} />
                <div>
                  <h2>{category.name}</h2>
                  <p>{category.description}</p>
                </div>
              </div>
              <span className="mono-label">{byCategory[category.id]?.length || 0} tasks</span>
            </div>
            <div className="suite-task-list">
              {(byCategory[category.id] || []).map((task) => (
                <button type="button" className="suite-task-row" key={task.id} onClick={() => onOpenTask(task)}>
                  <span className="task-number">{String(task.number).padStart(2, '0')}</span>
                  <span className="suite-task-copy">
                    <span className="suite-task-title">{task.title}</span>
                    <span className="suite-task-sub">{task.prompt}</span>
                  </span>
                  <span className={`difficulty difficulty-${task.difficulty}`}>{DIFFICULTY_LABEL[task.difficulty] || task.difficulty}</span>
                  <span className="task-check-count"><CheckCircle2 size={13} /> {task.checks.length}</span>
                  <span className="task-tool-count"><Wrench size={13} /> {task.tools.length}</span>
                  <span className="task-risk"><Shield size={13} /> {task.risk}</span>
                  <ArrowRight size={15} className="suite-task-arrow" />
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>

      <p className="page-footnote">
        <ClipboardList size={12} /> Task content is fictional and self-contained. No live customer data is used.
      </p>
    </div>
  )
}
