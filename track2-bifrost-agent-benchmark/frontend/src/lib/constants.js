export const FAILURE_LABELS = {
  policy_overreach: { label: 'Policy overreach', color: '#C23B2A' },
  identity_gap: { label: 'Identity gap', color: '#B7791F' },
  wrong_resolution: { label: 'Wrong resolution', color: '#3B6E8F' },
  tool_misuse: { label: 'Tool misuse', color: '#6B5B95' },
  unsafe_disclosure: { label: 'Unsafe disclosure', color: '#9B2C2C' },
  tone_escalation: { label: 'Tone escalation', color: '#8A6D3B' },
  no_escalation: { label: 'Missing escalation', color: '#4A5568' },
  safety_miss: { label: 'Safety miss', color: '#9B2C2C' },
  adapter_error: { label: 'Adapter error', color: '#5A6472' },
}

export const SCORE_WEIGHTS = [
  { id: 'task_success', label: 'Task success', weight: 35, note: 'Did the task pass?' },
  { id: 'policy', label: 'Policy', weight: 20, note: 'Did it follow the rules?' },
  { id: 'tool_accuracy', label: 'Tool accuracy', weight: 15, note: 'Did it use the right tools?' },
  { id: 'consistency', label: 'Consistency', weight: 15, note: 'Does it hold across trials?' },
  { id: 'safety', label: 'Safety', weight: 10, note: 'Did it protect the customer?' },
  { id: 'efficiency', label: 'Efficiency', weight: 5, note: 'Cost and latency.' },
]

export const CATEGORY_ICONS = {
  orders: 'Orders',
  returns: 'Returns',
  account: 'Access',
  policy: 'Policy',
}
