import Heading from '@theme/Heading';
import styles from './styles.module.css';

const highlights = [
  'Sherlock benchmark: 100% 回復率 (15/15)',
  'RepoAudit: F1 スコア 0.94、精度 88.9%',
  '独立発見の novel bugs: 4 件 (全例証済)',
  '監査コスト: ~$1.69 per bug',
];

export default function Paper() {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.heading}>研究論文</Heading>
        <p className={styles.lead}>
          分散プロトコル監査における仕様駆動の脆弱性検出手法を発表。
          マルチ実装環境で再利用可能な property vocabulary と
          specification-anchored framework により、コード解析単独では
          到達困難な不変式違反を特定。
        </p>

        <div className={styles.card}>
          <p className={styles.title}>
            Beyond Code Reasoning: Specification-Anchored Auditing of
            Multi-Implementation Distributed Protocols
          </p>
          <p className={styles.citation}>
            Kamba, Murakami, Sannai &middot;{' '}
            <a href="https://arxiv.org/abs/2604.26495" rel="noopener">
              arXiv:2604.26495
            </a>{' '}
            &middot; 2026
          </p>

          <ul className={styles.highlights}>
            {highlights.map((h, i) => (
              <li key={i} className={styles.highlightItem}>{h}</li>
            ))}
          </ul>

          <div className={styles.actions}>
            <a
              className={styles.action}
              href="https://arxiv.org/html/2604.26495v2"
              rel="noopener">
              arXiv で読む
            </a>
            <a
              className={styles.action}
              href="https://arxiv.org/pdf/2604.26495v2"
              rel="noopener">
              PDF をダウンロード
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
