import clsx from 'clsx';
import Heading from '@theme/Heading';
import Translate, {translate} from '@docusaurus/Translate';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: translate({
      id: 'homepage.feature1.title',
      message: '仕様駆動監査',
      description: 'HomepageFeatures: feature 1 title',
    }),
    description: (
      <Translate
        id="homepage.feature1.description"
        description="HomepageFeatures: feature 1 description">
        {'自然言語仕様 (EIP、コンセンサス仕様など) から型付きセキュリティプロパティ (Invariant / Precondition / Postcondition / Assumption) を抽出し、仕様レベルでしか表現できない脆弱性を検出します。'}
      </Translate>
    ),
  },
  {
    title: translate({
      id: 'homepage.feature2.title',
      message: 'Proof-Attempt 推論',
      description: 'HomepageFeatures: feature 2 title',
    }),
    description: (
      <Translate
        id="homepage.feature2.description"
        description="HomepageFeatures: feature 2 description">
        {'STRIDE + CWE Top 25 に基づく脅威モデルで整理した各プロパティに対し、「このプロパティが成立することを証明してみろ」と構造的に問い、仕様と実装のギャップを検出します。'}
      </Translate>
    ),
  },
  {
    title: translate({
      id: 'homepage.feature3.title',
      message: '完全な解釈可能性',
      description: 'HomepageFeatures: feature 3 title',
    }),
    description: (
      <Translate
        id="homepage.feature3.description"
        description="HomepageFeatures: feature 3 description">
        {'全監査ステップを JSON で構造化。3-gate review ループ (Dead Code / Trust Boundary / Scope) で偽陽性を根本原因ごとに分解し、監査可能・解釈可能な監査結果を提供します。'}
      </Translate>
    ),
  },
];

function Feature({title, description}) {
  return (
    <div className={clsx('col col--4', styles.feature)}>
      <Heading as="h3" className={styles.featureTitle}>{title}</Heading>
      <p className={styles.featureDescription}>{description}</p>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
