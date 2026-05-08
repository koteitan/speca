import Heading from '@theme/Heading';
import Translate, {translate} from '@docusaurus/Translate';
import styles from './styles.module.css';

const papers = [
  {
    slug: 'fusaka',
    title: translate({
      id: 'paper.fusaka.title',
      message: 'SPECA: 仕様書チェックリスト駆動の監査 — Ethereum クライアントのケーススタディ',
      description: 'Paper: fusaka title',
    }),
    citation: 'Kamba, Sannai · arXiv:2602.07513 · 2026',
    citationUrl: 'https://arxiv.org/abs/2602.07513',
    summary: translate({
      id: 'paper.fusaka.summary',
      message: 'SPECA の最初の論文。仕様書を「監査チェックリスト」に変換し、Ethereum Fusaka に参加する 11 クライアントへ適用した実戦ケーススタディ。',
      description: 'Paper: fusaka summary',
    }),
    highlights: [
      translate({
        id: 'paper.fusaka.highlight1',
        message: '実装間でチェックリストを使い回し、有効 finding の 76.5% をクロス実装由来に',
        description: 'Paper: fusaka highlight 1',
      }),
      translate({
        id: 'paper.fusaka.highlight2',
        message: 'Fusaka コンテストで valid finding 採択率 31.5% (平均 27.6% を上回る)',
        description: 'Paper: fusaka highlight 2',
      }),
      translate({
        id: 'paper.fusaka.highlight3',
        message: 'V2 再評価で High-severity 脆弱性 2/3 を検出',
        description: 'Paper: fusaka highlight 3',
      }),
      translate({
        id: 'paper.fusaka.highlight4',
        message: 'エージェント主導で submission 1 件あたり手動検証 40 分まで短縮',
        description: 'Paper: fusaka highlight 4',
      }),
    ],
    arxivHtml: 'https://arxiv.org/html/2602.07513v2',
    arxivPdf: 'https://arxiv.org/pdf/2602.07513v2',
  },
  {
    slug: 'multi-impl',
    title: translate({
      id: 'paper.multiImpl.title',
      message: 'コード推論を超えて — マルチ実装分散プロトコルの仕様アンカー監査',
      description: 'Paper: multi-impl title',
    }),
    citation: 'Kamba, Murakami, Sannai · arXiv:2604.26495 · 2026',
    citationUrl: 'https://arxiv.org/abs/2604.26495',
    summary: translate({
      id: 'paper.multiImpl.summary',
      message: 'Fusaka ケーススタディの仕組みを、Ethereum 以外を含むマルチ実装分散プロトコル全般に拡張した発展論文。',
      description: 'Paper: multi-impl summary',
    }),
    highlights: [
      translate({
        id: 'paper.multiImpl.highlight1',
        message: 'Sherlock 既知 H/M/L 脆弱性 15/15 を回復 (専門家補助あり)、自動のみだと 8/15',
        description: 'Paper: multi-impl highlight 1',
      }),
      translate({
        id: 'paper.multiImpl.highlight2',
        message: '366 名のコンテスト監査者が見落とした暗号アルゴリズムの不変条件違反を含む 4 件の未公開バグを独立発見',
        description: 'Paper: multi-impl highlight 2',
      }),
      translate({
        id: 'paper.multiImpl.highlight3',
        message: 'RepoAudit (C/C++ 15 プロジェクト): F1 = 0.94 / Precision 88.9% / Recall 100%',
        description: 'Paper: multi-impl highlight 3',
      }),
      translate({
        id: 'paper.multiImpl.highlight4',
        message: '1 バグあたりのコストは約 $1.69、H/M/L バグ 1 件あたり約 $30',
        description: 'Paper: multi-impl highlight 4',
      }),
    ],
    arxivHtml: 'https://arxiv.org/html/2604.26495v2',
    arxivPdf: 'https://arxiv.org/pdf/2604.26495v2',
  },
];

export default function Paper() {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.heading}>
          <Translate id="paper.heading" description="Paper section heading">研究論文</Translate>
        </Heading>
        <p className={styles.lead}>
          <Translate id="paper.lead" description="Paper section lead paragraph">
            SPECA は 2 本の研究論文に基づいて設計されています。最初の論文は Ethereum Fusaka 監査での実戦ケーススタディ、2 本目は同じ仕組みをマルチ実装分散プロトコル全般へ一般化した発展研究です。
          </Translate>
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
                  <Translate id="paper.readArxiv" description="Paper: read on arXiv link">arXiv で読む</Translate>
                </a>
                <a className={styles.action} href={p.arxivPdf} rel="noopener">
                  <Translate id="paper.pdf" description="Paper: PDF link">PDF</Translate>
                </a>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
