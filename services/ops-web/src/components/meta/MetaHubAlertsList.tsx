import Link from 'next/link';
import { opsWebLink } from '@/lib/meta/routes';
import type { FacebookHubAlert } from '@/lib/meta/types';

interface MetaHubAlertsListProps {
  alerts: FacebookHubAlert[];
}

export function MetaHubAlertsList({ alerts }: MetaHubAlertsListProps) {
  if (!alerts.length) return null;

  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <h2 style={{ marginTop: 0, fontSize: '1.1rem' }}>Alerts</h2>
      <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
        {alerts.map((alert) => (
          <li key={alert.message} style={{ marginBottom: '0.5rem' }}>
            <span className={alert.severity === 'danger' ? 'error' : 'muted'}>{alert.message}</span>{' '}
            <Link href={opsWebLink(alert.link)} className="nav-link">
              {alert.link_label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
