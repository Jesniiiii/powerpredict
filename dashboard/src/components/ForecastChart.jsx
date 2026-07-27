import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function ForecastChart({ data }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Load forecast</span>
        <span className="panel-tag">LIVE</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="power" stroke="var(--blue)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}