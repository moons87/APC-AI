import { useState } from "react";

const VERDICTS = {
  rework: {
    ru: "Вернуть на доработку",
    kk: "Қайта өңдеуге қайтарылсын",
    icon: "🔴",
    cls: "pc-vc-red",
  },
  partial: {
    ru: "Принять с частичными правками",
    kk: "Ішінара түзетумен қабылдансын",
    icon: "🟡",
    cls: "pc-vc-amber",
  },
  approved: {
    ru: "Полностью утвердить",
    kk: "Толық бекітілсін",
    icon: "🟢",
    cls: "pc-vc-green",
  },
};

function badgeClass(type) {
  const t = (type || "").toLowerCase();
  if (t.includes("дубл") || t.includes("dupl")) return "pc-b-amber";
  if (t.includes("блум") || t.includes("bloom")) return "pc-b-red";
  if (t.includes("логик") || t.includes("logic")) return "pc-b-coral";
  if (t.includes("пассив") || t.includes("passive")) return "pc-b-purple";
  return "pc-b-def";
}

export default function PlanResult({ plan, lang = "ru" }) {
  const [copied, setCopied] = useState(false);

  if (plan.status === "error") {
    return (
      <div className="state card--error">
        <div className="state__emoji">⚠️</div>
        <p className="state__title">Ошибка проверки</p>
        <p className="state__text">{plan.error_message || "Неизвестная ошибка"}</p>
      </div>
    );
  }

  const verdict = plan.verdict ? VERDICTS[plan.verdict] : null;
  const errors = plan.errors || [];

  const copy = async () => {
    if (!plan.optimized_plan) return;
    try {
      await navigator.clipboard.writeText(plan.optimized_plan);
    } catch {
      const el = document.createElement("textarea");
      el.value = plan.optimized_plan;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div className="pc-results">
      {verdict && (
        <div className={`pc-card ${verdict.cls}`}>
          <div className="pc-card__tag">РЕЗОЛЮЦИЯ</div>
          <div className="pc-verdict">
            <span className="pc-verdict__icon">{verdict.icon}</span>
            <div>
              <div className="pc-verdict__label">{verdict[lang] || verdict.ru}</div>
              {plan.summary && <p className="pc-verdict__sum">{plan.summary}</p>}
            </div>
          </div>
        </div>
      )}

      {!plan.is_raw && (
        <div className="pc-card">
          <div className="pc-card__tag">
            ВЫЯВЛЕННЫЕ ОШИБКИ
            {errors.length > 0 && <span className="pc-err-pill">{errors.length}</span>}
          </div>
          {errors.length === 0 ? (
            <div className="pc-no-errs">✓ Ошибок не выявлено</div>
          ) : (
            <ul className="pc-err-list">
              {errors.map((e, i) => (
                <li key={i} className="pc-err-item">
                  <div className="pc-err-top">
                    <span className="pc-err-n">{i + 1}</span>
                    <span className={`pc-badge ${badgeClass(e.type)}`}>{e.type}</span>
                  </div>
                  {e.description && <p className="pc-err-desc">{e.description}</p>}
                  {e.example && (
                    <>
                      <div className="pc-ex-lbl">Фрагмент:</div>
                      <div className="pc-ex-text">{e.example}</div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {plan.optimized_plan && (
        <div className="pc-card">
          <div className="pc-card__tag pc-card__tag--row">
            <span>{plan.is_raw ? "ОТВЕТ" : "ЭТАЛОННАЯ ВЕРСИЯ"}</span>
            <button className={`pc-copy${copied ? " pc-copy--ok" : ""}`} onClick={copy}>
              {copied ? "✓ Скопировано" : "📋 Копировать"}
            </button>
          </div>
          <pre className="pc-opt-text">{plan.optimized_plan}</pre>
        </div>
      )}
    </div>
  );
}
