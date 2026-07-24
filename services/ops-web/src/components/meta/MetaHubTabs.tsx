import type { MetaHubTab } from '@/lib/meta/types';

interface MetaHubTabsProps {
  tab: MetaHubTab;
  tabs: Array<{ id: MetaHubTab; label: string }>;
  onTabChange: (tab: MetaHubTab) => void;
  alertsOpenCount?: number;
}

export function MetaHubTabs({ tab, tabs, onTabChange, alertsOpenCount = 0 }: MetaHubTabsProps) {
  return (
    <div className="meta-hub-tabs" role="tablist" aria-label="Meta hub views">
      {tabs.map((item) => {
        const active = tab === item.id;
        const badge =
          item.id === 'alerts' && alertsOpenCount > 0 ? (
            <span className="meta-hub-tab-badge">{alertsOpenCount}</span>
          ) : null;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={`meta-hub-tab${active ? ' meta-hub-tab--active' : ''}`}
            onClick={() => onTabChange(item.id)}
          >
            {item.label}
            {badge}
          </button>
        );
      })}
    </div>
  );
}
