interface AlertCardProps {
  title: string;
  areas: string[];
  received_at: string;
}

export default function AlertCard({ title, areas, received_at }: AlertCardProps) {
  const time = new Date(received_at).toLocaleTimeString("he-IL");
  return (
    <div className="alert-card">
      <div className="alert-title">🚨 {title}</div>
      <div className="alert-areas">📍 {areas.join(", ")}</div>
      <div className="alert-time">🕐 {time}</div>
    </div>
  );
}
