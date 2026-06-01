import { useState } from "react";
import { checkPlan } from "../api.js";

export default function PlanForm({ onChecked, onCheckStart, onError }) {
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("ru");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Укажите название документа");
      return;
    }
    if (!text.trim() && !file) {
      setError("Вставьте текст плана или выберите файл");
      return;
    }
    setBusy(true);
    onCheckStart?.();
    try {
      const plan = await checkPlan({ title, language, text, file });
      onChecked(plan);
      setText("");
      setFile(null);
    } catch (err) {
      setError(err.message);
      onError?.(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card upload-form" onSubmit={submit}>
      <h3>Проверка учебного плана</h3>

      <label className="field">
        Название документа
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Напр.: РУП «Сварочное дело»"
        />
      </label>

      <label className="field">
        Язык анализа
        <select value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="ru">Русский</option>
          <option value="kk">Қазақша</option>
        </select>
      </label>

      <label className="field">
        Текст плана
        <textarea
          className="pc-textarea"
          rows={8}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Вставьте текст ОӘЖ / КТЖ / программы практики…"
        />
        <small className="field__hint">{text.length.toLocaleString()} символов</small>
      </label>

      <label className="field field--file">
        …или файл (.docx, .pdf, .xlsx, .txt)
        <input
          type="file"
          accept=".docx,.pdf,.xlsx,.txt"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
      </label>

      {error && <p className="form-error">{error}</p>}

      <button type="submit" className="btn" disabled={busy}>
        {busy ? "Методист анализирует…" : "🔍 Проверить"}
      </button>
    </form>
  );
}
