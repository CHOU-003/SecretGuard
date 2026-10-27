import { COMMON_STEPS, getRemediations } from '../../constants/remediation.js';

function Steps({ items }) {
  return (
    <ol className="list-decimal space-y-1.5 pl-5 text-sm text-fg/85">
      {items.map((s) => (
        <li key={s}>{s}</li>
      ))}
    </ol>
  );
}

export default function RemediationGuide({ findings }) {
  if (findings.length === 0) return null;
  const rules = getRemediations(findings.map((f) => f.secret_type));

  return (
    <section className="rounded-2xl border border-rim/70 bg-panel/60 p-5 backdrop-blur-sm">
      <h2 className="text-xl font-semibold text-fg">Hướng dẫn khắc phục</h2>
      <p className="mt-2 rounded-lg bg-caution/10 px-3 py-2 text-sm text-caution">
        Nếu commit đã được push lên remote, hãy xem như secret đã lộ: thu hồi key trước, dọn lịch sử git sau.
      </p>

      <div className="mt-5 space-y-5">
        {rules.map((rule) => (
          <div key={rule.key}>
            <h3 className="mb-2 text-sm font-semibold text-fg">{rule.title}</h3>
            <Steps items={rule.steps} />
          </div>
        ))}
        <div>
          <h3 className="mb-2 text-sm font-semibold text-fg">Gỡ secret khỏi code</h3>
          <Steps items={COMMON_STEPS} />
        </div>
      </div>
    </section>
  );
}
