import Sidebar from './Sidebar.jsx';
import Topbar from './Topbar.jsx';

export default function DashboardLayout({ children }) {
  return (
    <div className="dash-bg flex min-h-screen font-auth text-fg">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 space-y-6 p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}