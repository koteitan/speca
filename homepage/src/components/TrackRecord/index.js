import Heading from '@theme/Heading';
import styles from './styles.module.css';

const items = [
  'Sherlock コンテスト: 専門家の補助ありで既知 H/M/L 脆弱性 15 件すべて回復、完全自動だと 8 件 (53%)',
  'RepoAudit (C/C++ 15 プロジェクト): 既知 35 件のバグをすべて検出、F1 = 0.94 / 精度 88.9%',
  '独立発見した未公開バグ 4 件 — うち 1 件は 366 名のコンテスト監査者が見落とした暗号不変式違反',
  '1 バグあたり約 $1.69 / H/M/L バグ 1 件あたり約 $30、severity を落とさないフィルタで効率的な常時監視',
];

export default function TrackRecord() {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.heading}>実績</Heading>
        <p className={styles.lead}>
          研究論文での評価を通じて、コンテストの既知脆弱性を高い割合で
          回復できることと、加えて未公開バグを独立に発見できることが
          確認されています。RepoAudit ベンチマークでも精度 88.9% / 再現率 100% を達成し、
          1 バグあたり $1.69 という費用対効果を実証しました。
        </p>
        <ul className={styles.list}>
          {items.map((item, idx) => (
            <li key={idx} className={styles.item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
