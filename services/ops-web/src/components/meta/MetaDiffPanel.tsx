'use client';

interface MetaDiffPanelProps {
  oldValue: Record<string, unknown>;
  newValue: Record<string, unknown>;
}

export function MetaDiffPanel({ oldValue, newValue }: MetaDiffPanelProps) {
  const keys = Array.from(new Set([...Object.keys(oldValue), ...Object.keys(newValue)]));

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Diff review</h3>
      <table className="perf-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Old</th>
            <th>New</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const oldText = JSON.stringify(oldValue[key] ?? '');
            const newText = JSON.stringify(newValue[key] ?? '');
            const changed = oldText !== newText;
            return (
              <tr key={key}>
                <td>{key}</td>
                <td className={changed ? 'muted' : ''}>{oldText}</td>
                <td className={changed ? 'error' : ''}>{newText}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
