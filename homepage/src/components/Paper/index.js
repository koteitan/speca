import Heading from '@theme/Heading';
import styles from './styles.module.css';

const papers = [
  {
    slug: 'fusaka',
    title: 'SPECA: 仕様書チェックリスト駆動の監査 — Ethereum クライアントのケーススタディ',
    citation: 'Kamba, Sannai · arXiv:2602.07513 · 2026',
    citationUrl: 'https://arxiv.org/abs/2602.07513',
    summary: 'SPECA の最初の論文。仕様書を「監査チェックリスト」に変換し、Ethereum Fusaka に参加する 11 クライアントへ適用した実戦ケーススタディ。',
    highlights: [
      '実装間でチェックリストを使い回し、有効 finding の 76.5% をクロス実装由来に',
      'Fusaka コンテストで valid finding 採択率 31.5% (平均 27.6% を上回る)',
      'V2 再評価で High-severity 脆弱性 2/3 を検出',
      'エージェント主導で submission 1 件あたり手動検証 40 分まで短縮',
    ],
    arxivHtml: 'https://arxiv.org/html/2602.07513v2',
    arxivPdf: 'https://arxiv.org/pdf/2602.07513v2',
  },
  {
    slug: 'multi-impl',
    title: 'コード推論を超えて — マルチ実装分散プロトコルの仕様アンカー監査',
    citation: 'Kamba, Murakami, Sannai · arXiv:2604.26495 · 2026',
    citationUrl: 'https://arxiv.org/abs/2604.26495',
    summary: 'Fusaka ケーススタディの仕組みを、Ethereum 以外を含むマルチ実装分散プロトコル全般に拡張した発展論文。',
    highlights: [
      'Sherlock 既知 H/M/L 脆弱性 15/15 を回復 (専門家補助あり)、自動のみだと 8/15',
      '366 名のコンテスト監査者が見落とした暗号アルゴリズムの不変条件違反を含む 4 件の未公開バグを独立発見',
      'RepoAudit (C/C++ 15 プロジェクト): F1 = 0.94 / Precision 88.9% / Recall 100%',
      '1 バグあたりのコストは約 $1.69、H/M/L バグ 1 件あたり約 $30',
    ],
    arxivHtml: 'https://arxiv.org/html/2604.26495v2',
    arxivPdf: 'https://arxiv.org/pdf/2604.26495v2',
  },
];

export default function Paper() {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.heading}>研究論文</Heading>
        <p className={styles.lead}>
          SPECA は 2 本の研究論文に基づいて設計されています。最初の論文は
          Ethereum Fusaka 監査での実戦ケーススタディ、2 本目は同じ仕組みを
          マルチ実装分散プロトコル全般へ一般化した発展研究です。
        </p>

        <div className={styles.grid}>
          {papers.map((p) => (
            <article key={p.slug} className={styles.card}>
              <p className={styles.title}>{p.title}</p>
              <p className={styles.citation}>
                <a href={p.citationUrl} rel="noopener">{p.citation}</a>
              </p>
              <p className={styles.summary}>{p.summary}</p>
              <ul className={styles.highlights}>
                {p.highlights.map((h, i) => (
                  <li key={i} className={styles.highlightItem}>{h}</li>
                ))}
              </ul>
              <div className={styles.actions}>
                <a className={styles.action} href={p.arxivHtml} rel="noopener">
                  arXiv で読む
                </a>
                <a className={styles.action} href={p.arxivPdf} rel="noopener">
                  PDF
                </a>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
