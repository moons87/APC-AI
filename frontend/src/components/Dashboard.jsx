import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = {
  teacher: "#6366f1",
  student: "#10b981",
  open: "#0ea5e9",
  closed: "#f59e0b",
};

const STRUCTURE_LABELS = {
  intro: "Вступление / цель",
  explanation: "Объяснение материала",
  practice: "Закрепление / практика",
  summary: "Подведение итогов",
};

const TOOLTIP_STYLE = {
  borderRadius: 12,
  border: "1px solid #e7e9f0",
  boxShadow: "0 10px 30px rgba(20,22,28,0.12)",
  fontSize: 13,
  fontWeight: 600,
};

export default function Dashboard({ lesson }) {
  const r = lesson.result;
  if (!r) return null;

  const teacherPct = Math.round(r.teacher_talk_ratio * 100);
  const studentPct = Math.round(r.student_talk_ratio * 100);
  const conceptsTotal = r.covered_concepts.length + r.missing_concepts.length;
  const questionsTotal = r.open_questions + r.closed_questions;

  const talkData = [
    { name: "Преподаватель", value: teacherPct },
    { name: "Студенты", value: studentPct },
  ];

  const questionData = [
    { name: "Открытые", value: r.open_questions, fill: "url(#gradOpen)" },
    { name: "Закрытые", value: r.closed_questions, fill: "url(#gradClosed)" },
  ];

  return (
    <div className="dash">
      <div className="dash__head">
        <h2 className="dash__title">{lesson.title}</h2>
        <span className="chip">
          {lesson.language === "kk" ? "қазақша" : "русский"}
        </span>
      </div>

      <div className="metrics">
        <MetricCard
          label="Речь преподавателя"
          value={`${teacherPct}%`}
          ratio={r.teacher_talk_ratio}
        />
        <MetricCard
          label="Вопросов задано"
          value={r.total_questions}
          ratio={questionsTotal ? r.open_questions / questionsTotal : 0}
        />
        <MetricCard
          label="Понятий покрыто"
          value={conceptsTotal ? `${r.covered_concepts.length} / ${conceptsTotal}` : "—"}
          ratio={conceptsTotal ? r.covered_concepts.length / conceptsTotal : 0}
        />
      </div>

      <div className="panels">
        {/* Баланс речи — донат */}
        <div className="panel">
          <h3 className="panel__title">Баланс речи</h3>
          <ResponsiveContainer width="100%" height={236}>
            <PieChart>
              <defs>
                <linearGradient id="gradTeacher" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#818cf8" />
                  <stop offset="100%" stopColor="#4f46e5" />
                </linearGradient>
                <linearGradient id="gradStudent" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#34d399" />
                  <stop offset="100%" stopColor="#059669" />
                </linearGradient>
              </defs>
              <Pie
                data={talkData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={58}
                outerRadius={90}
                paddingAngle={3}
                cornerRadius={6}
                stroke="none"
                label={({ value }) => `${value}%`}
              >
                <Cell fill="url(#gradTeacher)" />
                <Cell fill="url(#gradStudent)" />
              </Pie>
              <Tooltip formatter={(v) => `${v}%`} contentStyle={TOOLTIP_STYLE} />
              <Legend iconType="circle" />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Типы вопросов — столбцы */}
        <div className="panel">
          <h3 className="panel__title">Типы вопросов</h3>
          <ResponsiveContainer width="100%" height={236}>
            <BarChart data={questionData} barCategoryGap="32%">
              <defs>
                <linearGradient id="gradOpen" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="100%" stopColor="#0284c7" />
                </linearGradient>
                <linearGradient id="gradClosed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fbbf24" />
                  <stop offset="100%" stopColor="#d97706" />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="name"
                tickLine={false}
                axisLine={{ stroke: "#e7e9f0" }}
                tick={{ fill: "#767c8c", fontSize: 12, fontWeight: 600 }}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                tick={{ fill: "#aab0bd", fontSize: 12 }}
              />
              <Tooltip
                cursor={{ fill: "rgba(99,102,241,0.06)" }}
                contentStyle={TOOLTIP_STYLE}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]} maxBarSize={88}>
                {questionData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Структура урока */}
        <div className="panel">
          <h3 className="panel__title">Структура урока</h3>
          <ul className="checks">
            {Object.entries(STRUCTURE_LABELS).map(([key, label]) => {
              const present = r.structure_present[key];
              return (
                <li key={key} className={`check${present ? "" : " check--missing"}`}>
                  <span className={`check__mark check__mark--${present ? "ok" : "no"}`}>
                    {present ? "✓" : "✕"}
                  </span>
                  {label}
                </li>
              );
            })}
          </ul>
        </div>

        {/* Покрытие плана */}
        <div className="panel">
          <h3 className="panel__title">Покрытие плана урока</h3>
          <ul className="checks">
            {r.covered_concepts.map((c) => (
              <li key={`c-${c}`} className="check">
                <span className="check__mark check__mark--ok">✓</span>
                {c}
              </li>
            ))}
            {r.missing_concepts.map((c) => (
              <li key={`m-${c}`} className="check check--missing">
                <span className="check__mark check__mark--no">✕</span>
                {c}
              </li>
            ))}
            {conceptsTotal === 0 && (
              <li className="check check--missing">Ключевые понятия не задавались</li>
            )}
          </ul>
        </div>
      </div>

      {/* Рекомендации */}
      <div className="panel panel--full">
        <h3 className="panel__title">Рекомендации</h3>
        <ol className="recs">
          {r.recommendations.map((rec, i) => (
            <li key={i}>{rec}</li>
          ))}
        </ol>
      </div>

      {lesson.transcript && (
        <details className="panel panel--full transcript-card">
          <summary>Показать транскрипт</summary>
          <pre className="transcript">{lesson.transcript}</pre>
        </details>
      )}
    </div>
  );
}

function MetricCard({ label, value, ratio = 0 }) {
  const pct = Math.max(0, Math.min(1, ratio)) * 100;
  return (
    <div className="metric">
      <div className="metric__value">{value}</div>
      <div className="metric__label">{label}</div>
      <div className="metric__bar">
        <div className="metric__bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
