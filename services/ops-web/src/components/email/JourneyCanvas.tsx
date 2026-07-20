'use client';

type GraphNode = { id: string; type: string; config?: Record<string, unknown> };
type GraphEdge = { from: string; to: string; label?: string };

const TYPE_CLASS: Record<string, string> = {
  trigger: 'email-journey-node--trigger',
  send: 'email-journey-node--send',
  wait: 'email-journey-node--wait',
  branch: 'email-journey-node--branch',
  exit: 'email-journey-node--exit',
};

export function JourneyCanvas({
  nodes,
  edges = [],
}: {
  nodes: GraphNode[];
  edges?: GraphEdge[];
}) {
  if (nodes.length === 0) {
    return <p className="muted">Chưa có bước trong journey graph.</p>;
  }
  return (
    <>
      <div className="email-journey-canvas email-journey-desktop" aria-label="Journey canvas">
        {nodes.map((node, index) => (
          <div key={node.id}>
            <div className={`email-journey-node ${TYPE_CLASS[node.type] ?? ''}`}>
              <p className="muted" style={{ margin: 0, fontSize: '0.72rem' }}>
                {node.type}
              </p>
              <strong>{node.id}</strong>
              {node.config && Object.keys(node.config).length > 0 ? (
                <pre style={{ margin: '0.35rem 0 0', fontSize: '0.7rem', opacity: 0.8 }}>
                  {JSON.stringify(node.config, null, 2)}
                </pre>
              ) : null}
            </div>
            {index < nodes.length - 1 ? <p className="muted" style={{ margin: '0.25rem 0 0 1rem' }}>↓</p> : null}
          </div>
        ))}
      </div>
      <ol className="email-journey-mobile" style={{ margin: 0, paddingLeft: '1.2rem' }}>
        {nodes.map((node) => (
          <li key={node.id} style={{ marginBottom: '0.5rem' }}>
            <strong>{node.type}</strong> — {node.id}
          </li>
        ))}
      </ol>
      {edges.length > 0 ? (
        <p className="muted" style={{ marginTop: '0.75rem', fontSize: '0.8rem' }}>
          {edges.map((e) => `${e.from}→${e.to}${e.label ? ` (${e.label})` : ''}`).join(' · ')}
        </p>
      ) : null}
      <style jsx>{`
        @media (max-width: 768px) {
          .email-journey-desktop { display: none; }
        }
        @media (min-width: 769px) {
          .email-journey-mobile { display: none; }
        }
      `}</style>
    </>
  );
}
