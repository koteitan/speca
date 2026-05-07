import Heading from '@theme/Heading';
import styles from './styles.module.css';

const items = [
  'Sherlock Ethereum Fusaka 監査: 既知脆弱性 15 件すべてを検出、追加バグ 4 件を独立発見',
  'RepoAudit C/C++ ベンチマーク: 他のバグ発見 AI と比較して高精度を維持しつつ新規候補バグ 12 件を報告',
  'Intmax ZK 実装、SP1 zkVM、Ethereum クライアント 20 件以上など多数のプロジェクトを監査',
];

export default function TrackRecord() {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.heading}>実績</Heading>
        <p className={styles.lead}>
          複数の本番環境プロジェクトおよびベンチマークでの検証を通じて、
          既知脆弱性の高い検出率と独立した新規バグ発見能力を確認しています。
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
