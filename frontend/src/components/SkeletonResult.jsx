// Скелетон результата проверки: имитирует будущие зоны (вердикт, сводка,
// карточки ошибок), пока Claude анализирует план (5–15 с). Снижает тревожность
// ожидания вместо пустой панели.
export default function SkeletonResult() {
  return (
    <div className="pc-results pc-skel" aria-busy="true" aria-label="Идёт анализ плана">
      <div className="pc-skel__verdict">
        <span className="pc-skel__circle" />
        <div className="pc-skel__col">
          <span className="pc-skel__line pc-skel__line--w30" />
          <span className="pc-skel__line pc-skel__line--w60" />
        </div>
      </div>

      <div className="pc-skel__alert">
        <span className="pc-skel__line" />
        <span className="pc-skel__line pc-skel__line--w70" />
      </div>

      {[0, 1, 2].map((i) => (
        <div className="pc-skel__card" key={i}>
          <span className="pc-skel__chip" />
          <span className="pc-skel__line pc-skel__line--w80" />
          <span className="pc-skel__quote" />
        </div>
      ))}
    </div>
  );
}
