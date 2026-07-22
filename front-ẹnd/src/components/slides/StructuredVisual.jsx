const COLORS = ['#14b8a6', '#6366f1', '#f59e0b', '#ec4899', '#22c55e'];

function cleanRows(table) {
  const headers = Array.isArray(table?.headers) ? table.headers.map(String) : [];
  const rows = Array.isArray(table?.rows) ? table.rows : [];
  return { headers, rows: rows.map((row) => Array.isArray(row) ? row : []).slice(0, 8) };
}

export function TableVisual({ table, theme }) {
  const { headers, rows } = cleanRows(table);
  if (!headers.length) return <div className="sv-empty">Không có dữ liệu bảng</div>;

  return (
    <div className="sv-table-wrap" style={{ borderColor: theme.surfaceBorder }}>
      <table className="sv-table" style={{ color: theme.text, fontFamily: theme.fontBody }}>
        <thead>
          <tr>{headers.map((header, index) => <th key={index} style={{ color: theme.text, background: theme.primary + '20' }}>{header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headers.map((_, colIndex) => <td key={colIndex} style={{ borderColor: theme.surfaceBorder }}>{String(row[colIndex] ?? '')}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function chartData(chart) {
  const labels = chart?.labels || chart?.categories || [];
  const rawSeries = Array.isArray(chart?.series) && chart.series.length
    ? chart.series
    : [{ name: chart?.title || 'Giá trị', values: chart?.values || [] }];
  const series = rawSeries.map((item, index) => ({
    name: item?.name || `Dữ liệu ${index + 1}`,
    values: (item?.values || item?.data || []).map((value) => Number(value) || 0),
  }));
  return { labels: labels.map(String), series };
}

export function ChartVisual({ chart, theme }) {
  const { labels, series } = chartData(chart);
  const type = String(chart?.chart_type || chart?.type || 'bar').toLowerCase();
  const allValues = series.flatMap((item) => item.values);
  const max = Math.max(...allValues.map(Math.abs), 1);
  const unit = chart?.unit ? ` ${chart.unit}` : '';

  if (!labels.length || !allValues.length) return <div className="sv-empty">Không có dữ liệu biểu đồ</div>;

  if (type === 'pie' || type === 'donut') {
    const values = series[0].values.slice(0, labels.length);
    const total = values.reduce((sum, value) => sum + Math.max(0, value), 0) || 1;
    const percentages = values.map((value) => Math.max(0, value) / total * 100);
    const stops = percentages.map((percentage, index) => {
      const start = percentages.slice(0, index).reduce((sum, value) => sum + value, 0);
      return `${COLORS[index % COLORS.length]} ${start}% ${start + percentage}%`;
    }).join(', ');
    return (
      <div className="sv-pie-layout">
        <div className="sv-pie" style={{ background: `conic-gradient(${stops})`, borderColor: theme.surfaceBorder }} />
        <div className="sv-legend">{labels.map((label, i) => <div key={label}><i style={{ background: COLORS[i % COLORS.length] }} />{label}<strong>{values[i] ?? 0}{unit}</strong></div>)}</div>
      </div>
    );
  }

  return (
    <div className="sv-chart">
      <div className="sv-plot">
        {labels.map((label, labelIndex) => (
          <div className="sv-group" key={`${label}-${labelIndex}`}>
            <div className="sv-bars">
              {series.map((item, seriesIndex) => {
                const value = item.values[labelIndex] || 0;
                return <div key={item.name} className="sv-bar" title={`${item.name}: ${value}${unit}`} style={{ height: `${Math.max(3, Math.abs(value) / max * 100)}%`, background: COLORS[seriesIndex % COLORS.length] }}><span>{value}</span></div>;
              })}
            </div>
            <div className="sv-label" style={{ color: theme.textSub }}>{label}</div>
          </div>
        ))}
      </div>
      {series.length > 1 && <div className="sv-series">{series.map((item, i) => <span key={item.name}><i style={{ background: COLORS[i % COLORS.length] }} />{item.name}</span>)}</div>}
    </div>
  );
}
