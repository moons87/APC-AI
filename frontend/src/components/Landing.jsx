import { useEffect, useRef, useState } from "react";

const TOPICS = [
  "Квадратные уравнения",
  "Фотосинтез растений",
  "Закон Ома",
  "Творчество Абая",
  "Архитектура компьютера",
];

const STEPS = [
  { n: "01", icon: "📝", t: "Тема", d: "Вы вводите только тему занятия — больше ничего." },
  { n: "02", icon: "🗂️", t: "План урока", d: "Claude строит план по шаблону вашего колледжа." },
  { n: "03", icon: "🔎", t: "Источники", d: "Подбор и структурирование материалов по теме." },
  { n: "04", icon: "🎞️", t: "Презентация", d: "Готовый слайд-дек, собранный по плану." },
  { n: "05", icon: "🎬", t: "Видео", d: "Обучающее видео с озвучкой на основе материала." },
  { n: "06", icon: "🎧", t: "Подкаст", d: "Аудиоверсия урока в формате живого диалога." },
];

const FEATURES = [
  { icon: "⚡", t: "10 минут вместо часов", d: "Полный комплект материалов к уроку — из одной темы." },
  { icon: "🎓", t: "Шаблон вашего колледжа", d: "План оформляется по принятой в учреждении структуре." },
  { icon: "🧩", t: "Единый поток", d: "План, слайды, видео и подкаст согласованы между собой." },
  { icon: "📊", t: "Анализ проведённого урока", d: "Загрузите запись — оценим баланс речи, вопросы, структуру." },
];

const OUTPUTS = [
  { icon: "🗂️", t: "План урока" },
  { icon: "🎞️", t: "Презентация" },
  { icon: "🎬", t: "Видео" },
  { icon: "🎧", t: "Подкаст" },
];

export default function Landing({ onEnter }) {
  useReveal();

  const scrollTo = (id) => () =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="lp">
      <div className="lp-aurora" aria-hidden="true">
        <span className="lp-blob lp-blob--1" />
        <span className="lp-blob lp-blob--2" />
        <span className="lp-blob lp-blob--3" />
        <span className="lp-grid" />
      </div>

      {/* Навигация */}
      <nav className="lp-nav">
        <div className="lp-logo">
          <span className="lp-logo__mark">🎧</span>
          <span className="lp-logo__text">Урок<span className="lp-logo__accent">·</span>Фабрика</span>
        </div>
        <div className="lp-nav__links">
          <button className="lp-link" onClick={scrollTo("how")}>Как это работает</button>
          <button className="lp-link" onClick={scrollTo("features")}>Возможности</button>
          <button className="lp-btn lp-btn--sm" onClick={onEnter}>Запустить</button>
        </div>
      </nav>

      {/* Герой */}
      <header className="lp-hero">
        <div className="lp-hero__copy">
          <span className="lp-eyebrow lp-pop" style={{ "--d": "0.05s" }}>
            ✦ Платформа ИИ для преподавателя
          </span>
          <h1 className="lp-title lp-pop" style={{ "--d": "0.12s" }}>
            Целый урок —
            <br />
            из одной <span className="lp-title__grad">темы</span>
          </h1>
          <p className="lp-lead lp-pop" style={{ "--d": "0.2s" }}>
            Введите тему — и за 10 минут получите <b>план</b>, <b>презентацию</b>,
            <b> обучающее видео</b> и <b>аудиоподкаст</b>. Плюс анализ качества
            проведённого занятия по записи.
          </p>
          <div className="lp-cta lp-pop" style={{ "--d": "0.28s" }}>
            <button className="lp-btn lp-btn--lg" onClick={() => onEnter("lesson")}>
              Запустить <span className="lp-btn__arrow">→</span>
            </button>
            <button
              className="lp-btn lp-btn--ghost lp-btn--lg"
              onClick={() => onEnter("plans")}
            >
              📋 Проверка плана
            </button>
            <button className="lp-btn lp-btn--ghost lp-btn--lg" onClick={scrollTo("how")}>
              Как это работает
            </button>
          </div>

          <div className="lp-stats lp-pop" style={{ "--d": "0.36s" }}>
            <Stat to={10} suffix=" мин" label="на полный урок" />
            <Stat to={4} suffix="" label="готовых артефакта" />
            <Stat to={1} suffix="" label="тема на входе" />
          </div>
        </div>

        {/* Визуальная сцена «тема → артефакты» */}
        <div className="lp-stage lp-pop" style={{ "--d": "0.22s" }}>
          <div className="lp-input">
            <span className="lp-input__label">Тема урока</span>
            <div className="lp-input__field">
              <Typewriter words={TOPICS} />
            </div>
            <span className="lp-input__spark">✦</span>
          </div>

          <div className="lp-flow" aria-hidden="true">
            <span className="lp-flow__line" />
            <span className="lp-flow__dot" />
          </div>

          <div className="lp-outputs">
            {OUTPUTS.map((o, i) => (
              <div
                key={o.t}
                className="lp-out"
                style={{ "--i": i, animationDelay: `${0.5 + i * 0.14}s` }}
              >
                <span className="lp-out__icon">{o.icon}</span>
                <span className="lp-out__t">{o.t}</span>
                <span className="lp-out__bar">
                  <i style={{ animationDelay: `${0.9 + i * 0.14}s` }} />
                </span>
              </div>
            ))}
          </div>
        </div>
      </header>

      {/* Пайплайн */}
      <section className="lp-section" id="how">
        <div className="lp-head reveal">
          <span className="lp-kicker">Как это работает</span>
          <h2 className="lp-h2">Шесть шагов от темы до готового урока</h2>
        </div>
        <ol className="lp-pipe">
          {STEPS.map((s, i) => (
            <li
              className="lp-step reveal"
              key={s.n}
              style={{ transitionDelay: `${i * 0.07}s` }}
            >
              <span className="lp-step__num">{s.n}</span>
              <span className="lp-step__icon">{s.icon}</span>
              <h3 className="lp-step__t">{s.t}</h3>
              <p className="lp-step__d">{s.d}</p>
              {i < STEPS.length - 1 && <span className="lp-step__arrow" aria-hidden="true">→</span>}
            </li>
          ))}
        </ol>
      </section>

      {/* Возможности */}
      <section className="lp-section" id="features">
        <div className="lp-head reveal">
          <span className="lp-kicker">Возможности</span>
          <h2 className="lp-h2">Почему это экономит часы работы</h2>
        </div>
        <div className="lp-features">
          {FEATURES.map((f, i) => (
            <article
              className="lp-feature reveal"
              key={f.t}
              style={{ transitionDelay: `${i * 0.08}s` }}
            >
              <span className="lp-feature__icon">{f.icon}</span>
              <h3 className="lp-feature__t">{f.t}</h3>
              <p className="lp-feature__d">{f.d}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Модуль анализа */}
      <section className="lp-section">
        <div className="lp-band reveal">
          <div className="lp-band__copy">
            <span className="lp-kicker">Уже работает</span>
            <h2 className="lp-h2">Анализ проведённого урока</h2>
            <p className="lp-band__text">
              Загрузите аудио- или видеозапись занятия — система оценит баланс речи
              преподавателя и студентов, типы вопросов, покрытие плана и структуру
              урока, и даст конкретные рекомендации.
            </p>
            <button className="lp-btn lp-btn--lg" onClick={onEnter}>
              Открыть анализатор <span className="lp-btn__arrow">→</span>
            </button>
          </div>
          <div className="lp-band__viz" aria-hidden="true">
            <div className="lp-mini">
              <div className="lp-mini__val">72%</div>
              <div className="lp-mini__lbl">речь преподавателя</div>
              <span className="lp-mini__bar"><i /></span>
            </div>
            <div className="lp-mini">
              <div className="lp-mini__val">18</div>
              <div className="lp-mini__lbl">вопросов</div>
              <span className="lp-mini__bar"><i style={{ width: "60%" }} /></span>
            </div>
            <div className="lp-mini lp-mini--wide">
              <div className="lp-mini__lbl">Структура урока</div>
              <div className="lp-mini__chips">
                <span>✓ Вступление</span>
                <span>✓ Объяснение</span>
                <span>✓ Практика</span>
                <span className="is-off">✕ Итог</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Финальный CTA */}
      <section className="lp-section">
        <div className="lp-final reveal">
          <h2 className="lp-final__t">Соберите первый урок за 10 минут</h2>
          <p className="lp-final__d">Одна тема на входе — комплект материалов на выходе.</p>
          <button className="lp-btn lp-btn--xl" onClick={onEnter}>
            Запустить платформу <span className="lp-btn__arrow">→</span>
          </button>
        </div>
      </section>

      <footer className="lp-footer">
        <span>🎧 Урок·Фабрика</span>
        <span className="lp-footer__muted">ИИ-ассистент преподавателя · {new Date().getFullYear()}</span>
      </footer>
    </div>
  );
}

/* ---------- Вспомогательные ---------- */

function Typewriter({ words }) {
  const [i, setI] = useState(0);
  const [txt, setTxt] = useState("");
  const [del, setDel] = useState(false);

  useEffect(() => {
    const full = words[i % words.length];
    let t;
    if (!del && txt.length < full.length) {
      t = setTimeout(() => setTxt(full.slice(0, txt.length + 1)), 65);
    } else if (!del && txt.length === full.length) {
      t = setTimeout(() => setDel(true), 1500);
    } else if (del && txt.length > 0) {
      t = setTimeout(() => setTxt(full.slice(0, txt.length - 1)), 32);
    } else {
      setDel(false);
      setI((p) => p + 1);
    }
    return () => clearTimeout(t);
  }, [txt, del, i, words]);

  return (
    <span className="lp-type">
      {txt}
      <span className="lp-caret" />
    </span>
  );
}

function Stat({ to, suffix, label }) {
  const ref = useRef(null);
  const [v, setV] = useState(0);
  const done = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !done.current) {
            done.current = true;
            const start = performance.now();
            const dur = 1300;
            const tick = (now) => {
              const p = Math.min(1, (now - start) / dur);
              const eased = 1 - Math.pow(1 - p, 3);
              setV(Math.round(eased * to));
              if (p < 1) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
          }
        });
      },
      { threshold: 0.6 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [to]);

  return (
    <div className="lp-stat" ref={ref}>
      <span className="lp-stat__num">
        {v}
        {suffix}
      </span>
      <span className="lp-stat__lbl">{label}</span>
    </div>
  );
}

/* Scroll-reveal через IntersectionObserver — без зависимостей. */
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      els.forEach((el) => el.classList.add("is-in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.16 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}
