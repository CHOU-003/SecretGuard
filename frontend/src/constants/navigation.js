import { HomeIcon, ClockIcon } from '../components/common/icons.jsx';

// soon: true -> hiển thị mờ + nhãn "Sắp có" (chưa có route). Bỏ cờ này khi đã làm trang.
export const NAV_ITEMS = [
  { label: 'Tổng quan', to: '/', icon: HomeIcon },
  { label: 'Lịch sử quét', to: '/history', icon: ClockIcon, soon: true },
];
