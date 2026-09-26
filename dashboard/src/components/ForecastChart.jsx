import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function ForecastChart({ data }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Load forecast</span>
        <span className="panel-tag">LIVE</span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <defs>
            <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--blue-light)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--blue-light)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} width={40} />
          <Tooltip
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 12, color: 'var(--text)', boxShadow: 'var(--shadow)' }}
            labelStyle={{ color: 'var(--text)' }}
          />
          <Area
            type="monotone"
            dataKey="power"
            stroke="var(--blue)"
            strokeWidth={2.5}
            fill="url(#forecastFill)"
            dot={false}
            activeDot={{ r: 4, fill: 'var(--blue)', stroke: 'var(--surface)', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}