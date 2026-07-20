'use client';

import { useMemo, useState } from 'react';
import { JourneyCanvas } from './JourneyCanvas';

type GraphNode = { id: string; type: string; config?: Record<string, unknown> };
type GraphEdge = { from: string; to: string; label?: string };

type GraphJson = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

const NODE_TYPES = ['trigger', 'wait', 'send', 'branch', 'exit'] as const;

function defaultConfig(type: string): Record<string, unknown> {
  if (type === 'wait') return { delay_hours: 24 };
  if (type === 'send') return { template_id: null };
  if (type === 'branch') return { condition_type: 'opened', within_hours: 168 };
  if (type === 'trigger') return { trigger_type: 'segment_enter' };
  return {};
}

export function JourneyCanvasEditor({
  graph,
  editable,
  onSave,
}: {
  graph: GraphJson;
  editable: boolean;
  onSave?: (next: GraphJson) => Promise<void> | void;
}) {
  const [draft, setDraft] = useState<GraphJson>(graph);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const nodes = draft.nodes ?? [];
  const edges = draft.edges ?? [];

  const nodeIds = useMemo(() => new Set(nodes.map((n) => n.id)), [nodes]);

  function updateNode(index: number, patch: Partial<GraphNode>) {
    setDraft((prev) => {
      const nextNodes = [...(prev.nodes ?? [])];
      nextNodes[index] = { ...nextNodes[index], ...patch };
      return { ...prev, nodes: nextNodes };
    });
  }

  function updateNodeConfig(index: number, key: string, value: unknown) {
    setDraft((prev) => {
      const nextNodes = [...(prev.nodes ?? [])];
      const node = nextNodes[index];
      nextNodes[index] = {
        ...node,
        config: { ...(node.config ?? {}), [key]: value },
      };
      return { ...prev, nodes: nextNodes };
    });
  }

  function addNode(type: string) {
    const id = `${type}_${nodes.length + 1}`;
    setDraft((prev) => ({
      nodes: [...(prev.nodes ?? []), { id, type, config: defaultConfig(type) }],
      edges: prev.edges ?? [],
    }));
  }

  function removeNode(index: number) {
    const nodeId = nodes[index]?.id;
    setDraft((prev) => ({
      nodes: (prev.nodes ?? []).filter((_, i) => i !== index),
      edges: (prev.edges ?? []).filter((e) => e.from !== nodeId && e.to !== nodeId),
    }));
  }

  function addEdge(from: string, to: string, label = 'default') {
    if (!from || !to || from === to) return;
    setDraft((prev) => ({
      ...prev,
      edges: [...(prev.edges ?? []), { from, to, label }],
    }));
  }

  async function save() {
    if (!onSave) return;
    setSaving(true);
    setError('');
    try {
      await onSave(draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lưu journey thất bại');
    } finally {
      setSaving(false);
    }
  }

  if (!editable) {
    return <JourneyCanvas nodes={nodes} edges={edges} />;
  }

  return (
    <div>
      {error ? <p className="error">{error}</p> : null}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        {NODE_TYPES.map((type) => (
          <button key={type} type="button" className="btn btn-secondary btn-sm" onClick={() => addNode(type)}>
            + {type}
          </button>
        ))}
        {onSave ? (
          <button type="button" className="btn btn-sm" disabled={saving} onClick={() => void save()}>
            {saving ? '…' : 'Lưu graph'}
          </button>
        ) : null}
      </div>

      {nodes.map((node, index) => (
        <div key={node.id} className="card" style={{ marginBottom: '0.75rem', padding: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
            <strong>{node.type}</strong>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => removeNode(index)}>
              Xóa
            </button>
          </div>
          <label className="muted" style={{ display: 'block', marginTop: '0.5rem' }}>
            Step id
            <input
              className="input"
              value={node.id}
              onChange={(e) => updateNode(index, { id: e.target.value.trim() })}
              style={{ width: '100%', marginTop: '0.25rem' }}
            />
          </label>
          {node.type === 'wait' ? (
            <label className="muted" style={{ display: 'block', marginTop: '0.5rem' }}>
              Delay (hours)
              <input
                className="input"
                type="number"
                min={1}
                value={Number(node.config?.delay_hours ?? 24)}
                onChange={(e) => updateNodeConfig(index, 'delay_hours', Number(e.target.value))}
                style={{ width: '100%', marginTop: '0.25rem' }}
              />
            </label>
          ) : null}
          {node.type === 'send' ? (
            <label className="muted" style={{ display: 'block', marginTop: '0.5rem' }}>
              Template ID
              <input
                className="input"
                value={String(node.config?.template_id ?? '')}
                onChange={(e) => updateNodeConfig(index, 'template_id', e.target.value || null)}
                style={{ width: '100%', marginTop: '0.25rem' }}
              />
            </label>
          ) : null}
          {node.type === 'branch' ? (
            <>
              <label className="muted" style={{ display: 'block', marginTop: '0.5rem' }}>
                Condition
                <select
                  className="input"
                  value={String(node.config?.condition_type ?? 'opened')}
                  onChange={(e) => updateNodeConfig(index, 'condition_type', e.target.value)}
                  style={{ width: '100%', marginTop: '0.25rem' }}
                >
                  <option value="opened">opened</option>
                  <option value="clicked">clicked</option>
                  <option value="lifecycle">lifecycle</option>
                </select>
              </label>
              <label className="muted" style={{ display: 'block', marginTop: '0.5rem' }}>
                Within hours
                <input
                  className="input"
                  type="number"
                  min={1}
                  value={Number(node.config?.within_hours ?? 168)}
                  onChange={(e) => updateNodeConfig(index, 'within_hours', Number(e.target.value))}
                  style={{ width: '100%', marginTop: '0.25rem' }}
                />
              </label>
            </>
          ) : null}
          {node.type === 'trigger' ? (
            <label className="muted" style={{ display: 'block', marginTop: '0.5rem' }}>
              Trigger type
              <select
                className="input"
                value={String(node.config?.trigger_type ?? 'segment_enter')}
                onChange={(e) => updateNodeConfig(index, 'trigger_type', e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem' }}
              >
                <option value="segment_enter">segment_enter</option>
                <option value="event_open">event_open</option>
                <option value="event_click">event_click</option>
              </select>
            </label>
          ) : null}
        </div>
      ))}

      <div className="card" style={{ padding: '0.75rem' }}>
        <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Edges</h3>
        <JourneyCanvas nodes={nodes} edges={edges} />
        <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.75rem' }}>
          <EdgeAddForm nodeIds={nodeIds} onAdd={addEdge} />
          {(edges ?? []).map((edge, idx) => (
            <p key={`${edge.from}-${edge.to}-${idx}`} className="muted" style={{ margin: 0 }}>
              {edge.from} → {edge.to} {edge.label ? `(${edge.label})` : ''}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

function EdgeAddForm({
  nodeIds,
  onAdd,
}: {
  nodeIds: Set<string>;
  onAdd: (from: string, to: string, label: string) => void;
}) {
  const ids = [...nodeIds];
  const [from, setFrom] = useState(ids[0] ?? '');
  const [to, setTo] = useState(ids[1] ?? ids[0] ?? '');
  const [label, setLabel] = useState('default');

  return (
    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'end' }}>
      <label className="muted">
        From
        <select className="input" value={from} onChange={(e) => setFrom(e.target.value)}>
          {ids.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      </label>
      <label className="muted">
        To
        <select className="input" value={to} onChange={(e) => setTo(e.target.value)}>
          {ids.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      </label>
      <label className="muted">
        Label
        <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} />
      </label>
      <button type="button" className="btn btn-secondary btn-sm" onClick={() => onAdd(from, to, label)}>
        Thêm edge
      </button>
    </div>
  );
}
