// Базовый URL бэкенда. В docker-compose задаётся через VITE_API_URL.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function uploadLesson({ title, language, keyConcepts, file }) {
  const form = new FormData();
  form.append("title", title);
  form.append("language", language);
  form.append("key_concepts", keyConcepts); // строка: понятия через перенос/запятую
  form.append("file", file);

  const res = await fetch(`${API_URL}/lessons/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Ошибка загрузки: ${res.status} ${text}`);
  }
  return res.json(); // { lesson_id, status }
}

export async function getLesson(id) {
  const res = await fetch(`${API_URL}/lessons/${id}`);
  if (!res.ok) throw new Error(`Не удалось получить урок ${id}`);
  return res.json();
}

export async function listLessons() {
  const res = await fetch(`${API_URL}/lessons`);
  if (!res.ok) throw new Error("Не удалось получить список уроков");
  return res.json();
}

export async function checkPlan({ title, language, text, file }) {
  const form = new FormData();
  form.append("title", title);
  form.append("language", language);
  if (text) form.append("text", text);
  if (file) form.append("file", file);

  const res = await fetch(`${API_URL}/plans/check`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ошибка проверки: ${res.status} ${body}`);
  }
  return res.json();
}

export async function listPlans() {
  const res = await fetch(`${API_URL}/plans`);
  if (!res.ok) throw new Error("Не удалось получить список проверок");
  return res.json();
}

export async function getPlan(id) {
  const res = await fetch(`${API_URL}/plans/${id}`);
  if (!res.ok) throw new Error(`Не удалось получить проверку ${id}`);
  return res.json();
}
