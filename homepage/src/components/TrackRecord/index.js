import Heading from '@theme/Heading';
import styles from './styles.module.css';

const items = [
  'Sherlock: expert augmented で 15/15 の脆弱性回復、automated-only 8/15 (53%)',
  'RepoAudit (C/C++): precision 88.9%、recall 100%、F1=0.94、35 既知脆弱性全検出',
  'Novel bug discovery: 4 件独立発見、1 件は 366 名監査者が見落とした暗号不変式違反',
  'Cost efficiency: ~$1.69 per bug、severity 保持フィルタ下での cost-effective monitoring',
];

export default function TrackRecord() {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.heading}>実績</Heading>
        <p className={styles.lead}>
          論文検証により、expert augmented 時の full recovery (15/15) と
          automated-only (8/15) の実運用性能を定量化。RepoAudit 15 プロジェクト
          全体で precision 88.9%、recall 100% を達成し、cost-per-bug $1.69 を実証。
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
