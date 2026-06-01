import { useCallback, useEffect, useState } from "react";
import PlanForm from "./PlanForm.jsx";
import PlanResult from "./PlanResult.jsx";
import SkeletonResult from "./SkeletonResult.jsx";
import { getPlan, listPlans } from "../api.js";

// Проверка плана синхронная и терминальная, поэтому точки статичные
// (без «пульсации» dot--processing, которая означала бы «ещё обрабатывается»).
const VERDICT_DOT = {
  rework: "pc-dot--red",
  partial: "pc-dot--amber",
  approved: "pc-dot--green",
};

export default function PlanCheckPage() {
  const [plans, setPlans] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setPlans(await listPlans());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Старт проверки: показываем скелетон вместо прошлого/пустого результата.
  const handleCheckStart = () => {
    setSelected(null);
    setLoading(true);
  };

  const handleChecked = (plan) => {
    setLoading(false);
    setSelected(plan);
    refresh();
  };

  const handleError = () => setLoading(false);

  const openPlan = async (id) => {
    setLoading(false);
    try {
      setSelected(await getPlan(id));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <PlanForm
          onCheckStart={handleCheckStart}
          onChecked={handleChecked}
          onError={handleError}
        />

        <div className="card">
          <h3 className="sidebar__heading">История проверок</h3>
          <ul className="lessons">
            {plans.length === 0 && (
              <li className="lessons__empty">Пока пусто — проверьте первый план.</li>
            )}
            {plans.map((p) => (
              <li
                key={p.id}
                className={
                  "lessons__item" +
                  (selected && p.id === selected.id ? " lessons__item--active" : "")
                }
                onClick={() => openPlan(p.id)}
              >
                <span
                  className={`dot ${VERDICT_DOT[p.verdict] || "pc-dot--none"}`}
                />
                <span className="lessons__title">{p.title}</span>
                <span className="lessons__status">{p.language}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="content content--scroll">
        {loading ? (
          <SkeletonResult />
        ) : selected ? (
          <PlanResult plan={selected} lang={selected.language} />
        ) : (
          <div className="state">
            <div className="state__emoji">📋</div>
            <p className="state__title">Здесь появится результат проверки</p>
            <p className="state__text">
              Вставьте текст плана или загрузите файл слева и нажмите «Проверить».
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
