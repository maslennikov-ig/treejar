/** Shared chart tokens for the CRM dashboard light and dark themes. */

export const CHART_TOOLTIP_STYLE: React.CSSProperties = {
    backgroundColor: 'var(--admin-chart-tooltip-bg)',
    border: '1px solid var(--admin-chart-tooltip-border)',
    borderRadius: '12px',
    color: 'var(--admin-chart-tooltip-text)',
    fontSize: '13px',
    boxShadow: 'var(--admin-chart-shadow)',
};

export const CHART_CARD_CLASS =
    'admin-chart-card rounded-2xl p-6';
export const CHART_TITLE_CLASS = 'text-lg font-semibold text-[var(--admin-chart-title)]';
export const CHART_META_CLASS = 'text-sm text-[var(--admin-chart-muted)]';
export const CHART_SUBTITLE_CLASS = 'mb-2 text-center text-xs text-[var(--admin-chart-muted)]';
export const CHART_EMPTY_CLASS = 'flex items-center justify-center text-sm text-[var(--admin-chart-empty)]';
export const CHART_LEGEND_STYLE: React.CSSProperties = {
    color: 'var(--admin-chart-muted)',
    fontSize: '12px',
};
export const CHART_GRID_STROKE = 'var(--admin-chart-grid)';
export const CHART_AXIS_STROKE = 'var(--admin-chart-axis)';
export const CHART_AXIS_FONT_SIZE = 12;
