import styles from './styles.module.css';

const lines = [
  {prompt: '$', cmd: 'npm install -g speca-cli'},
  {prompt: '$', cmd: 'speca auth login'},
  {prompt: '$', cmd: 'speca init'},
  {prompt: '$', cmd: 'speca run --target 04'},
];

export default function TerminalMockup() {
  return (
    <div className={styles.frame} role="figure" aria-label="SPECA CLI usage example">
      <div className={styles.titlebar}>
        <span className={styles.dot} data-color="r" aria-hidden="true" />
        <span className={styles.dot} data-color="y" aria-hidden="true" />
        <span className={styles.dot} data-color="g" aria-hidden="true" />
        <span className={styles.title}>SPECA CLI</span>
      </div>
      <pre className={styles.body}>
        {lines.map((line, idx) => (
          <code key={idx} className={styles.line}>
            <span className={styles.prompt}>{line.prompt}</span>
            <span className={styles.cmd}>{line.cmd}</span>
          </code>
        ))}
      </pre>
    </div>
  );
}
