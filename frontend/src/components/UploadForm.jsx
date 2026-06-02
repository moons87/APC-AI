import { useState } from "react";
import { extractPlanFields, uploadLesson } from "../api.js";

const MAX_UPLOAD_MB = 2048;

export default function UploadForm({ onUploaded }) {
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("ru");
  const [keyConcepts, setKeyConcepts] = useState("");
  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [planFile, setPlanFile] = useState(null);
  const [planText, setPlanText] = useState("");
  const [parsing, setParsing] = useState(false);

  const handleParsePlan = async () => {
    setError("");
    if (!planFile && !planText.trim()) {
      setError("Приложите файл плана или вставьте его текст");
      return;
    }
    setParsing(true);
    try {
      const { title: t, key_concepts } = await extractPlanFields({
        file: planFile,
        text: planText.trim(),
        language,
      });
      if (t) setTitle(t);
      setKeyConcepts((key_concepts || []).join("\n"));
    } catch (err) {
      setError(err.message);
    } finally {
      setParsing(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!file) {
      setError("Выберите аудио- или видеофайл урока");
      return;
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`Файл больше ${MAX_UPLOAD_MB} МБ`);
      return;
    }
    if (!title.trim()) {
      setError("Укажите тему урока");
      return;
    }
    setSubmitting(true);
    try {
      const { lesson_id } = await uploadLesson({
        title: title.trim(),
        language,
        keyConcepts,
        file,
      });
      // Сбрасываем форму и сообщаем родителю.
      setTitle("");
      setKeyConcepts("");
      setFile(null);
      e.target.reset();
      onUploaded(lesson_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="card upload-form" onSubmit={handleSubmit}>
      <h3>Новый урок</h3>

      <div className="field plan-import">
        <span className="plan-import__title">План урока (необязательно)</span>
        <input
          type="file"
          accept=".docx,.pdf,.xlsx,.txt"
          onChange={(e) => setPlanFile(e.target.files[0] || null)}
        />
        <small className="field__hint">docx, pdf, xlsx, txt</small>
        <textarea
          rows={3}
          value={planText}
          onChange={(e) => setPlanText(e.target.value)}
          placeholder="…или вставьте текст плана"
        />
        <button
          type="button"
          className="btn btn--secondary"
          onClick={handleParsePlan}
          disabled={parsing}
        >
          {parsing ? "Разбираю план…" : "Разобрать план → заполнить поля"}
        </button>
      </div>

      <label className="field">
        Тема урока
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Напр.: Квадратные уравнения"
        />
      </label>

      <label className="field">
        Язык записи
        <select value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="ru">Русский</option>
          <option value="kk">Қазақша</option>
        </select>
      </label>

      <label className="field">
        Ключевые понятия плана (по одному на строку)
        <textarea
          rows={4}
          value={keyConcepts}
          onChange={(e) => setKeyConcepts(e.target.value)}
          placeholder={"дискриминант\nтеорема Виета\nкорни уравнения"}
        />
      </label>

      <label className="field field--file">
        Аудио или видео урока
        <input
          type="file"
          accept=".mp3,.wav,.m4a,.ogg,.flac,audio/*,.mp4,.mov,.mkv,.webm,video/*"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
        <small className="field__hint">
          Аудио: mp3, wav, m4a, ogg, flac. Видео: mp4, mov, mkv, webm. До 2 ГБ.
        </small>
      </label>

      {error && <p className="form-error">{error}</p>}

      <button type="submit" className="btn" disabled={submitting}>
        {submitting ? "Загрузка…" : "Загрузить и проанализировать"}
      </button>
    </form>
  );
}
