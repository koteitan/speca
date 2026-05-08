import Heading from '@theme/Heading';
import CodeBlock from '@theme/CodeBlock';
import styles from './styles.module.css';

export default function QuickStart() {
  return (
    <section className={styles.section}>
      <div className="container">
        <Heading as="h2" className={styles.heading}>はじめる</Heading>
        <p className={styles.lead}>
          リポジトリを clone して、Python オーケストレータを直接実行するか、
          npm 経由で SPECA を起動できます。Go / Rust / Nim / TypeScript / C
          などマルチ言語対応で、GitHub Actions による完全自動化に対応しています。
        </p>

        <div className={styles.block}>
          <h3 className={styles.subheading}>Python オーケストレータを直接実行</h3>
          <CodeBlock language="bash">
            uv run python3 scripts/run_phase.py --target 04 --workers 4 --max-concurrent 64
          </CodeBlock>
        </div>

        <div className={styles.block}>
          <h3 className={styles.subheading}>speca-cli を使用 (npm 公開予定)</h3>
          <CodeBlock language="bash">
            {`npx speca-cli init
npx speca-cli run --target 04
npx speca-cli browse`}
          </CodeBlock>
        </div>
      </div>
    </section>
  );
}
