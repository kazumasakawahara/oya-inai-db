import { StatsCards } from "@/components/domain/StatsCards";
import { RenewalAlerts } from "@/components/domain/RenewalAlerts";
import { RecentActivity } from "@/components/domain/RecentActivity";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">ダッシュボード</h2>
      <StatsCards />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RenewalAlerts />
        <RecentActivity />
      </div>
    </div>
  );
}
