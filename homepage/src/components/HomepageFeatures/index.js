import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    title: 'Spec-driven',
    description: (
      <>
        SPECA transforms specifications (BIPs, EIPs, RFCs, design docs) into
        formal program graphs and security properties. Findings cite the spec
        clause they came from.
      </>
    ),
  },
  {
    title: 'Proof-based audit',
    description: (
      <>
        A three-phase Map → Prove → Stress-Test pipeline runs Claude Code agents
        against the target codebase. Gaps in proof become candidate findings;
        budget and circuit breakers keep cost bounded.
      </>
    ),
  },
  {
    title: 'Recall-safe filtering',
    description: (
      <>
        A 3-gate FP filter (Dead Code → Trust Boundary → Scope Check) preserves
        real findings. Only these three gates may dispute a verdict, so audit
        recall is never silently traded away.
      </>
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
