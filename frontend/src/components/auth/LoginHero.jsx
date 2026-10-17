export default function LoginHero() {
  return (
    <div>
      <h1 className="text-4xl font-semibold leading-tight tracking-tight text-fg sm:text-5xl">
        Bảo vệ mã nguồn
        <span className="block bg-linear-to-r from-[#1AA6FF] to-[#5B4BFF] bg-clip-text text-transparent">
          An toàn từ đầu
        </span>
      </h1>
      <p className="mt-5 text-base text-fg-muted">Phát hiện secret trước khi triển khai.</p>
    </div>
  );
}