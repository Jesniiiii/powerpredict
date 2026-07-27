export default function ThemeToggle({ theme, onToggle }) {
  return (
    <div className="theme-toggle" onClick={onToggle}>
      <div className="theme-toggle-knob"></div>
    </div>
  );
}