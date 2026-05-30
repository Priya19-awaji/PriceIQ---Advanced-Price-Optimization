import { ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface KPICardProps {
  label: string;
  value: string;
  subtitle?: string;
  trend?: number;
  icon?: ReactNode;
  variant?: 'default' | 'navy' | 'accent';
}

export function KPICard({ label, value, subtitle, trend, icon, variant = 'default' }: KPICardProps) {
  const baseClass = variant === 'navy'
    ? 'navy-panel'
    : variant === 'accent'
      ? 'dashboard-card border-l-4 border-l-accent'
      : 'dashboard-card';

  return (
    <div className={`${baseClass} flex flex-col gap-1 animate-fade-in`}>
      <div className="flex items-center justify-between">
        <span className={`kpi-label ${variant === 'navy' ? 'text-navy-foreground/60' : ''}`}>{label}</span>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      <span className={`kpi-value ${variant === 'navy' ? 'text-navy-foreground' : 'text-foreground'}`}>{value}</span>
      <div className="flex items-center gap-1">
        {trend !== undefined && (
          <span className={`flex items-center gap-0.5 text-xs font-medium ${trend > 0 ? 'text-success' : trend < 0 ? 'text-destructive' : 'text-muted-foreground'}`}>
            {trend > 0 ? <TrendingUp size={12} /> : trend < 0 ? <TrendingDown size={12} /> : <Minus size={12} />}
            {trend > 0 ? '+' : ''}{trend.toFixed(1)}%
          </span>
        )}
        {subtitle && <span className={`text-xs ${variant === 'navy' ? 'text-navy-foreground/50' : 'text-muted-foreground'}`}>{subtitle}</span>}
      </div>
    </div>
  );
}
