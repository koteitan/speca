import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';
import Translate from '@docusaurus/Translate';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import TrackRecord from '@site/src/components/TrackRecord';
import QuickStart from '@site/src/components/QuickStart';
import Paper from '@site/src/components/Paper';
import TerminalMockup from '@site/src/components/TerminalMockup';

import Heading from '@theme/Heading';
import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  const logoUrl = useBaseUrl('/img/speca_logo.svg');
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <img
          src={logoUrl}
          alt="SPECA"
          width="120"
          height="120"
          className={styles.heroLogo}
        />
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link
            className="button button--secondary button--lg"
            to="/docs/intro">
            <Translate id="hero.docs" description="hero CTA: read docs">ドキュメントを読む</Translate>
          </Link>
          <Link
            className={clsx('button button--secondary button--lg', styles.secondaryCta)}
            href="https://github.com/NyxFoundation/speca">
            <Translate id="hero.github" description="hero CTA: view on GitHub">GitHub で見る</Translate>
          </Link>
        </div>
        <TerminalMockup />
      </div>
    </header>
  );
}

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title={siteConfig.title}
      description={siteConfig.tagline}>
      <HomepageHeader />
      <main>
        <HomepageFeatures />
        <TrackRecord />
        <Paper />
        <QuickStart />
      </main>
    </Layout>
  );
}
