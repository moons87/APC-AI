import { useCallback, useEffect, useState } from "react";
import PlanForm from "./PlanForm.jsx";
import PlanResult from "./PlanResult.jsx";
import { getPlan, listPlans } from "../api.js";

const VERDICT_DOT = {
  rework: "dot--error",
  partial: "dot--processing",
  approved: "dot--done",
};

export default function PlanCheckPage() {
  const [plans, setPlans] = useState([]);
  const [selected, setSelected] = useState(null);

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

  const handleChecked = (plan) => {
    setSelected(plan);
    refresh();
  };

  const openPlan = async (id) => {
    try {
      setSelected(await getPlan(id));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="layout">
      <aside className="sidebar">
        <PlanForm onChecked={handleChecked} />

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
                  className={`dot ${VERDICT_DOT[p.verdict] || "dot--pending"}`}
                />
                <span className="lessons__title">{p.title}</span>
                <span className="lessons__status">{p.language}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="content">
        {selected ? (
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
