import { useCallback, useEffect, useRef, useState } from "react";
import UploadForm from "./components/UploadForm.jsx";
import Dashboard from "./components/Dashboard.jsx";
import Landing from "./components/Landing.jsx";
import { getLesson, listLessons } from "./api.js";

const STATUS_LABELS = {
  pending: "в очереди",
  processing: "обрабатывается",
  done: "готово",
  error: "ошибка",
};

export default function App() {
  const [view, setView] = useState("landing");
  const [lessons, setLessons] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedLesson, setSelectedLesson] = useState(null);
  const pollRef = useRef(null);

  const refreshList = useCallback(async () => {
    try {
      setLessons(await listLessons());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  // Поллинг выбранного урока, пока он не завершится.
  useEffect(() => {
    if (selectedId == null) return;

    let cancelled = false;
    const tick = async () => {
      try {
        const lesson = await getLesson(selectedId);
        if (cancelled) return;
        setSelectedLesson(lesson);
        refreshList();
        if (lesson.status === "done" || lesson.status === "error") {
          clearInterval(pollRef.current);
        }
      } catch (e) {
        console.error(e);
      }
    };

    tick();
    pollRef.current = setInterval(tick, 3000);
    return () => {
      cancelled = true;
      clearInterval(pollRef.current);
    };
  }, [selectedId, refreshList]);

  const handleUploaded = (lessonId) => {
    setSelectedId(lessonId);
    setSelectedLesson(null);
    refreshList();
  };

  if (view === "landing") {
    return <Landing onEnter={() => setView("app")} />;
  }

  return (
    <div className="app">
      <button className="app__home" onClick={() => setView("landing")}>
        ← На главную
      </button>
      <header className="masthead">
        <span className="masthead__eyebrow">🎧 Анализ урока · ИИ</span>
        <h1 className="masthead__title">ИИ-наблюдатель урока</h1>
        <p className="masthead__sub">
          Загрузите аудио- или видеозапись занятия — система оценит баланс речи,
          вовлечённость, типы вопросов, покрытие плана и структуру урока.
        </p>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <UploadForm onUploaded={handleUploaded} />

          <div className="card">
            <h3 className="sidebar__heading">История уроков</h3>
            <ul className="lessons">
              {lessons.length === 0 && (
                <li className="lessons__empty">Пока пусто — загрузите первый урок.</li>
              )}
              {lessons.map((l) => (
                <li
                  key={l.id}
                  className={
                    "lessons__item" +
                    (l.id === selectedId ? " lessons__item--active" : "")
                  }
                  onClick={() => setSelectedId(l.id)}
                >
                  <span className={`dot dot--${l.status}`} />
                  <span className="lessons__title">{l.title}</span>
                  <span className="lessons__status">
                    {STATUS_LABELS[l.status] || l.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <main className="content">
          {selectedLesson ? (
            <LessonView lesson={selectedLesson} />
          ) : (
            <div className="state">
              <div className="state__emoji">📊</div>
              <p className="state__title">Здесь появится дашборд урока</p>
              <p className="state__text">
                Выберите урок в истории слева или загрузите новую запись занятия.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function LessonView({ lesson }) {
  if (lesson.status === "error") {
    return (
      <div className="state card--error">
        <div className="state__emoji">⚠️</div>
        <p className="state__title">Ошибка обработки</p>
        <p className="state__text">{lesson.error_message || "Неизвестная ошибка"}</p>
      </div>
    );
  }

  if (lesson.status !== "done") {
    return (
      <div className="state">
        <div className="spinner" />
        <p className="state__title">{lesson.title}</p>
        <p className="state__text">
          Статус: {STATUS_LABELS[lesson.status] || lesson.status}… Идёт
          транскрибация и анализ — это может занять несколько минут в зависимости
          от длины записи.
        </p>
      </div>
    );
  }

  return <Dashboard lesson={lesson} />;
}
