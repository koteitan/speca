// SettingsPage — `/settings`.
//
// v0 surface (per UI_DESIGN.md Slice G):
//   1. Auth status   — read-only summary of the active login method.
//   2. Integrations  — `code` / `gh` presence + auth probe.
//   3. Maintenance   — three <OpenInVSCode> launchers for the absolute
//      paths the backend surfaces via /api/integrations/paths.
//
// The page is intentionally read-only in v0; writes (logout, key rotation,
// repo picker) land in v1. Every action that could fail is gated on the
// data being loaded — we render a thin spinner placeholder if the
// integrations paths query is still in flight rather than mounting a
// disabled <OpenInVSCode> with an empty `path`.

import type { ReactElement } from "react";

import { OpenInVSCode } from "@/components/OpenInVSCode";
import { useAuthStatus } from "@/features/auth/useAuth";
import {
  useIntegrationsPaths,
  useIntegrationsStatus,
} from "@/features/integrations/useIntegrationsStatus";

import styles from "./SettingsPage.module.css";

function StatusDot({ ok }: { ok: boolean | null }): ReactElement {
  const cls =
    ok === true
      ? styles.dotOk
      : ok === false
        ? styles.dotMissing
        : styles.dotUnknown;
  return <span className={`${styles.dot} ${cls}`} aria-hidden="true" />;
}

function AuthSection(): ReactElement {
  const { data, isPending, isError } = useAuthStatus();

  if (isPending) {
    return <p className={styles.muted}>Loading auth status…</p>;
  }
  if (isError || !data) {
    return (
      <p className={styles.muted}>auth status の取得に失敗しました。</p>
    );
  }

  const methodLabel =
    data.method === "oauth"
      ? "Claude.ai OAuth"
      : data.method === "api_key"
        ? "Anthropic API key"
        : "なし";

  return (
    <dl className={styles.kv} data-testid="settings-auth-block">
      <div className={styles.kvRow}>
        <dt>ログイン状態</dt>
        <dd>
          <StatusDot ok={data.logged_in} />{" "}
          {data.logged_in ? "ログイン済み" : "未ログイン"}
        </dd>
      </div>
      <div className={styles.kvRow}>
        <dt>方式</dt>
        <dd>{methodLabel}</dd>
      </div>
      {data.identity ? (
        <div className={styles.kvRow}>
          <dt>identity</dt>
          <dd>
            <code>{data.identity}</code>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

function IntegrationsSection(): ReactElement {
  const { data, isPending, isError } = useIntegrationsStatus();

  if (isPending) {
    return <p className={styles.muted}>Loading integrations…</p>;
  }
  if (isError || !data) {
    return (
      <p className={styles.muted}>
        integrations status の取得に失敗しました。
      </p>
    );
  }

  return (
    <dl className={styles.kv} data-testid="settings-integrations-block">
      <div className={styles.kvRow}>
        <dt>VSCode CLI (`code`)</dt>
        <dd>
          <StatusDot ok={data.code.installed} />{" "}
          {data.code.installed
            ? data.code.version ?? "installed"
            : "見つかりません"}
        </dd>
      </div>
      <div className={styles.kvRow}>
        <dt>GitHub CLI (`gh`)</dt>
        <dd>
          <StatusDot ok={data.gh.installed} />{" "}
          {data.gh.installed
            ? data.gh.version ?? "installed"
            : "見つかりません"}
        </dd>
      </div>
      {data.gh.installed ? (
        <div className={styles.kvRow}>
          <dt>`gh auth`</dt>
          <dd>
            <StatusDot ok={data.gh.authed} />{" "}
            {data.gh.authed === true
              ? "ログイン済み"
              : data.gh.authed === false
                ? "未ログイン"
                : "不明"}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

function MaintenanceSection(): ReactElement {
  const { data, isPending, isError } = useIntegrationsPaths();

  if (isPending) {
    return <p className={styles.muted}>Loading paths…</p>;
  }
  if (isError || !data) {
    return (
      <p className={styles.muted}>paths の取得に失敗しました。</p>
    );
  }

  return (
    <div className={styles.actions} data-testid="settings-maintenance-block">
      <OpenInVSCode
        path={data.speca_dir}
        label=".speca/ を VSCode で開く"
        variant="button"
      />
      <OpenInVSCode
        path={data.repo_root}
        label="リポジトリを VSCode で開く"
        variant="button"
      />
      <OpenInVSCode
        path={data.claude_dir}
        label="~/.claude/ を VSCode で開く"
        variant="button"
      />
    </div>
  );
}

export function SettingsPage(): ReactElement {
  return (
    <section className={styles.page} data-testid="settings-page">
      <header className={styles.header}>
        <h1 className={styles.title}>Settings</h1>
        <p className={styles.subtitle}>
          v0 は read-only。書き込み系の設定 (logout、API key 変更、target
          repo picker) は v1 で対応予定。
        </p>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Auth</h2>
        <AuthSection />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Integrations</h2>
        <IntegrationsSection />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Maintenance</h2>
        <p className={styles.sectionHint}>
          設定ファイルや run state を VSCode で開きます。VSCode CLI
          (`code`) が PATH 上に必要です。
        </p>
        <MaintenanceSection />
      </section>
    </section>
  );
}

export default SettingsPage;
