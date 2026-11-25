import { HomeIcon, ClockIcon,ProjectIcon, AuditLogIcon } from '../components/common/icons.jsx';

export const NAV_ITEMS = [
  { label: 'Tổng quan', to: '/', icon: HomeIcon },
  { label: 'Quản lý dự án', to: '/projects', icon: ProjectIcon },
  { label: 'Nhật ký thay đổi', to: '/audit-log', icon: AuditLogIcon },
  { label: 'Lịch sử quét', to: '/history', icon: ClockIcon},
];
