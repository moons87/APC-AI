import { useMemo, useState } from "react";

// Вердикт: крупный статус-бейдж. Подпись локализуется по языку анализа.
const VERDICTS = {
  rework: {
    ru: "Требуется доработка",
    kk: "Қайта өңдеу қажет",
    icon: "⚠️",
    cls: "pcv--rework",
  },
  partial: {
    ru: "Принять с правками",
    kk: "Түзетумен қабылдау",
    icon: "🟡",
    cls: "pcv--partial",
  },
  approved: {
    ru: "Полностью утверждён",
    kk: "Толық бекітілген",
    icon: "✅",
    cls: "pcv--approved",
  },
};

// Стабильные коды категорий ↔ цвет бейджа + локализованная подпись чипа.
const CATEGORIES = {
  duplicate: { ru: "Дубликаты", kk: "Дубликаттар", cls: "pcb--amber" },
  bloom: { ru: "Ошибка Блума", kk: "Блум қатесі", cls: "pcb--red" },
  logic: { ru: "Логика", kk: "Логика бұзылуы", cls: "pcb--coral" },
  passive: { ru: "Пассив", kk: "Пассивті тұжырым", cls: "pcb--purple" },
  other: { ru: "Прочее", kk: "Басқа", cls: "pcb--def" },
};

// Если модель не прислала category — выводим код из текста метки (оба языка).
function resolveCategory(err) {
  if (err.category && CATEGORIES[err.category]) return err.category;
  const t = (err.type || "").toLowerCase();
  if (t.includes("дубл") || t.includes("dupl")) return "duplicate";
  if (t.includes("блум") || t.includes("bloom")) return "bloom";
  if (t.includes("логик") || t.includes("logic")) return "logic";
  if (t.includes("пассив") || t.includes("passive")) return "passive";
  return "other";
}

function ChipCopy({ text }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard недоступен — молча игнорируем */
    }
    setDone(true);
    setTimeout(() => setDone(false), 1600);
  };
  return (
    <button
      className={`pc-fix${done ? " pc-fix--ok" : ""}`}
      onClick={copy}
      title="Скопировать замену"
    >
      {done ? "✓ Скопировано" : text}
    </button>
  );
}

function ErrorCard({ err, lang, index }) {
  const [open, setOpen] = useState(true);
  const cat = resolveCategory(err);
  const meta = CATEGORIES[cat];
  const label = err.type || meta[lang] || meta.ru;
  const suggestions = err.suggestions || [];

  return (
    <div className={`pc-ecard${open ? " is-open" : ""}`}>
      <button className="pc-ecard__head" onClick={() => setOpen((o) => !o)}>
        <span className="pc-ecard__n">{index + 1}</span>
        <span className={`pc-badge ${meta.cls}`}>{label}</span>
        <span className="pc-ecard__chev" aria-hidden="true">
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open && (
        <div className="pc-ecard__body">
          {err.description && <p className="pc-ecard__desc">{err.description}</p>}

          {err.example && <blockquote className="pc-quote">{err.example}</blockquote>}

          {suggestions.length > 0 && (
            <div className="pc-fixes">
              <span className="pc-fixes__lbl">💡 Варианты замены:</span>
              <div className="pc-fixes__row">
                {suggestions.map((s, i) => (
                  <ChipCopy key={i} text={s} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PlanResult({ plan, lang = "ru" }) {
  const [copied, setCopied] = useState(false);
  const [activeCat, setActiveCat] = useState(null);

  const errors = useMemo(() => plan.errors || [], [plan.errors]);

  // Счётчики по категориям для чипов-фильтра (только реально присутствующие).
  const counts = useMemo(() => {
    const c = {};
    for (const e of errors) {
      const cat = resolveCategory(e);
      c[cat] = (c[cat] || 0) + 1;
    }
    return c;
  }, [errors]);

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
  const visible = activeCat
    ? errors.filter((e) => resolveCategory(e) === activeCat)
    : errors;

  const copyPlan = async () => {
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
      {/* Блок 1 — Вердикт */}
      {verdict && (
        <div className={`pc-verdict ${verdict.cls}`}>
          <span className="pc-verdict__icon">{verdict.icon}</span>
          <div className="pc-verdict__text">
            <span className="pc-verdict__eyebrow">Статус</span>
            <span className="pc-verdict__label">{verdict[lang] || verdict.ru}</span>
          </div>
        </div>
      )}

      {/* Блок 2 — Сводка (alert) */}
      {plan.summary && (
        <div className="pc-alert">
          <span className="pc-alert__icon">ℹ️</span>
          <p className="pc-alert__text">{plan.summary}</p>
        </div>
      )}

      {/* Блок 3 — Ошибки (фильтр + карточки), скрыт при raw-фолбэке */}
      {!plan.is_raw && (
        <div className="pc-errors">
          <div className="pc-errors__bar">
            <span className="pc-errors__title">
              Ошибки{errors.length > 0 ? ` · ${errors.length}` : ""}
            </span>
            {errors.length > 0 && (
              <div className="pc-filter">
                <button
                  className={`pc-chip${activeCat === null ? " is-active" : ""}`}
                  onClick={() => setActiveCat(null)}
                >
                  Все {errors.length}
                </button>
                {Object.keys(CATEGORIES)
                  .filter((cat) => counts[cat])
                  .map((cat) => (
                    <button
                      key={cat}
                      className={`pc-chip${activeCat === cat ? " is-active" : ""}`}
                      onClick={() => setActiveCat(cat)}
                    >
                      {CATEGORIES[cat][lang] || CATEGORIES[cat].ru} {counts[cat]}
                    </button>
                  ))}
              </div>
            )}
          </div>

          {errors.length === 0 ? (
            <div className="pc-no-errs">✓ Ошибок не выявлено</div>
          ) : (
            <div className="pc-ecards">
              {visible.map((e) => (
                <ErrorCard
                  key={errors.indexOf(e)}
                  err={e}
                  lang={lang}
                  index={errors.indexOf(e)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Эталонная версия / сырой ответ */}
      {plan.optimized_plan && (
        <div className="pc-card">
          <div className="pc-card__tag pc-card__tag--row">
            <span>{plan.is_raw ? "ОТВЕТ" : "ЭТАЛОННАЯ ВЕРСИЯ"}</span>
            <button
              className={`pc-copy${copied ? " pc-copy--ok" : ""}`}
              onClick={copyPlan}
            >
              {copied ? "✓ Скопировано" : "📋 Копировать"}
            </button>
          </div>
          <pre className="pc-opt-text">{plan.optimized_plan}</pre>
        </div>
      )}
    </div>
  );
}
