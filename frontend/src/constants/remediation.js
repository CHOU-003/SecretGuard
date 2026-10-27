const normalize = (t = '') => t.toLowerCase().replace(/[_\s-]+/g, ' ').trim();

// Khớp theo thứ tự; rule cuối là mặc định. secret_type trong DB đang có cả
// "AWS_KEY" và "AWS Access Key" nên chuẩn hoá trước khi so khớp.
const RULES = [
  {
    key: 'aws',
    match: (t) => t.startsWith('aws'),
    title: 'AWS Access Key',
    steps: [
      'Vô hiệu hoá rồi xoá access key trong IAM → Security credentials.',
      'Tạo key mới và lưu bằng biến môi trường hoặc AWS Secrets Manager.',
      'Kiểm tra CloudTrail xem key có bị dùng trái phép không.',
    ],
  },
  {
    key: 'generic',
    match: () => true,
    title: 'API key / token',
    steps: [
      'Thu hồi (revoke) key tại nhà cung cấp dịch vụ rồi cấp key mới.',
      'Rà soát log của dịch vụ để phát hiện truy cập bất thường.',
    ],
  },
];

export const COMMON_STEPS = [
  'Xoá secret khỏi code, đọc từ biến môi trường (.env đã thêm vào .gitignore) hoặc secret manager.',
  'Chưa push: sửa commit bằng git commit --amend rồi quét lại.',
  'Đã push: dùng git filter-repo hoặc BFG để xoá khỏi lịch sử, sau đó force-push và báo cả nhóm.',
];

export function getRemediations(types) {
  const found = new Map();
  for (const type of types) {
    const rule = RULES.find((r) => r.match(normalize(type)));
    if (rule) found.set(rule.key, rule);
  }
  return [...found.values()];
}
