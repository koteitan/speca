# speca-cli テスト手順

`speca-cli` をローカルで動作確認する手順。リリース前 / コントリビュータが手元で挙動を確かめたいときに使う。

CI が回す自動テスト (vitest) は `npm test` 一発で済むが、本ドキュメントは **エンドツーエンドの手動 smoke テスト** までカバーする。

---

## 0. 前提

- Node 20 以上(推奨 22)
- npm
- `uv`(Python 側を呼ぶため。`speca run` だけ使う)
- `git`
- `claude` CLI(`speca doctor` / `speca ask` で使う。なければ WARN 表示)
- リポジトリの `dev` ブランチをチェックアウト済みであること

```bash
git clone https://github.com/NyxFoundation/speca.git
cd speca
git checkout dev
cd cli
npm install
npm run build      # sync-schemas → tsc
```

---

## 1. ユニットテスト (vitest)

最初に必ずこれが緑になることを確認する。

```bash
npm test
```

**期待:** `Tests 220 passed (220)` / `Test Files 24 passed (24)`

落ちる場合は `npm run typecheck` でビルドエラーを確認、`node_modules` を消して `npm install` し直す。

---

## 2. CLI smoke テスト

すべて `cli/` ディレクトリから実行する想定。

### 2.1 version

```bash
node dist/cli.js version
```

**期待:** `v1.0.0` が枠付きで表示される。

### 2.2 doctor

```bash
node dist/cli.js doctor
```

**期待:** Node / uv / git / claude のバージョンが `[OK]` で並び、auth 未ログインなら `[WARN]` で `Run \`speca auth login\`` の hint が出る。

### 2.3 auth status(未ログイン状態)

```bash
node dist/cli.js auth status
```

**期待:** `Not logged in. Run \`speca auth login\`.` + `No accounts found`。

### 2.4 auth login --help

```bash
node dist/cli.js auth login --help
```

**期待:** OAuth paste-code フローと `--api-key` fallback の説明が表示。

> 実 OAuth 試行はブラウザ操作 + コード貼り付けが必要なので smoke では割愛。subscription 持ちなら `node dist/cli.js auth login` を実行 → 表示された URL を開いてログイン → コードを貼り付けて Enter。

### 2.5 init(非対話モード)

```bash
TMP=$(mktemp -d)
node dist/cli.js init \
  --target-repo "https://github.com/sigp/lighthouse" \
  --target-language Rust \
  --target-layer consensus \
  --rubric default \
  --output-dir "$TMP" \
  --non-interactive --yes \
  --project-name "lighthouse-test"

ls "$TMP"
```

**期待:** `TARGET_INFO.json` と `BUG_BOUNTY_SCOPE.json` の 2 ファイルが生成される。

### 2.6 init で生成された JSON が U2 schema を満たすことを確認

```bash
node -e "
import('./dist/lib/schemas/index.js').then(async (m) => {
  const fs = await import('node:fs/promises');
  const dir = process.env.TMP;
  const ti = JSON.parse(await fs.readFile(dir + '/TARGET_INFO.json', 'utf8'));
  const bb = JSON.parse(await fs.readFile(dir + '/BUG_BOUNTY_SCOPE.json', 'utf8'));
  console.log('TARGET_INFO  validate:', m.validateTargetInfo(ti).ok);
  console.log('BUG_BOUNTY   validate:', m.validateBugBountyScope(bb).ok);
});
"
```

**期待:** `TARGET_INFO validate: true` / `BUG_BOUNTY validate: true`。

### 2.7 run --json(依存解決失敗で正常 fail)

リポジトリルートから:

```bash
cd ..
SPECA_OUTPUT_DIR=tmp-test-out node cli/dist/cli.js run --phase 01b --json 2>/dev/null
rm -rf tmp-test-out
```

**期待:** stdout に NDJSON 4 イベント:

```json
{"type":"pipeline-started", ...}
{"type":"phase-started", "phase":"01b", ...}
{"type":"phase-failed", "phase":"01b", "reason":"dependency check failed", ...}
{"type":"pipeline-completed", "results":{"01b":false}, ...}
```

各イベントに `ts` フィールド(ISO-UTC)が付いていれば M6 の `emitJson` envelope が効いている。

> 実 phase の完走テストは Claude Code subscription + 監査対象リポの clone が必要。CI では別途 `01b` の dependency-failure シナリオで NDJSON シーケンスを assertion している。

### 2.8 browse --no-tui(fixture を読む)

```bash
cd cli
node dist/cli.js browse "test/fixtures/04_PARTIAL_*.json" --no-tui --severity High
```

**期待:**

```
speca browse: 1/6 findings (filter: severity:High)
  [High] CONFIRMED_VULNERABILITY  PROP-vault-inv-001  All 3 gates passed.
```

### 2.9 browse --json(NDJSON pass-through)

```bash
node dist/cli.js browse "test/fixtures/04_PARTIAL_*.json" --json --severity Critical
```

**期待:** 1 行目が `{"type":"browse-summary", ...}`、続いてマッチした finding ごとに `{"type":"finding", ...}` が NDJSON で 1 行ずつ。

### 2.10 ask --help

```bash
node dist/cli.js ask --help
```

**期待:** `--from` / `--session` / `--max-context` / `--no-tui` の説明と例。

### 2.11 ask --no-tui(stdin 経由、claude 必要)

```bash
echo "Why is this a vulnerability?" | \
  node dist/cli.js ask --from test/fixtures/finding.json --no-tui --max-context 5000
```

**期待(claude にログイン済みの場合):** Claude の応答テキストが stdout に出力される。

> `claude` CLI がインストールされていない、またはログインしていない場合はエラー終了する。事前に `claude` CLI を入れて `claude /login` でログインしておくこと(`speca auth login` で対応する場合は別)。

---

## 3. TUI モードの目視確認

`--no-tui` を付けない場合 Ink の TUI が起動する。これらは TTY が要るので CI では assertion せず、目視で確認する。

```bash
node dist/cli.js doctor                              # 枠付きの診断画面
node dist/cli.js auth status                         # アカウント表示
node dist/cli.js init                                # 対話 wizard (clack)
node dist/cli.js run --phase 01a                     # ダッシュボード(未認証なら失敗)
node dist/cli.js browse outputs/04_PARTIAL_*.json    # 検出結果ブラウザ
node dist/cli.js ask --from outputs/04_PARTIAL_*.json # チャット UI
```

各 TUI 画面のキーバインドは `cli/README.md` 参照。

### テーマ切り替え確認

`~/.config/speca/config.toml`(Windows: `%APPDATA%\speca\config.toml`)を作成:

```toml
theme = "light"   # or "dark" / "solarized"

[keybinds]
exit = ["q", "ctrl+c"]
toggle-log = ["l"]
```

`speca run` / `speca browse` / `speca ask` を起動して色味が変わることを確認。

---

## 4. パッケージング確認

```bash
cd cli
npm pack --dry-run
```

**期待:** `name: speca-cli`, `version: 1.0.0`, `total files: ~200`, `package size: ~150kB`。

実際の発行(リリース時のみ):

```bash
npm publish              # NyxFoundation org のメンバ + 2FA token が必要
```

---

## 5. クロス OS 確認

CI は GitHub Actions の matrix で `ubuntu-22.04` / `macos-14` / `windows-2022` × Node 20 / 22 を回している。手元で別 OS の挙動を見たい場合:

- Windows: ネイティブで動く(`claude.cmd` shim 自動解決済み)
- macOS: brew で `node@22 uv git` を入れて手順通り
- Linux: `apt install nodejs npm` + `curl -LsSf https://astral.sh/uv/install.sh | sh`

OS 固有のハマりどころは `docs/hiro/cli-quickstart.md` の Windows セクション参照。

---

## 6. 既知の制約(v1.0/v1.1 時点)

- `speca run` の **TUI ダッシュボード経由での実 phase 完走** はテストに入っていない(claude subscription + 監査対象 clone が要る)。**CI は dependency-failure シナリオの NDJSON シーケンス検証のみ**。
- M4 (browse) と M5 (ask) の `useInput` → `useKeybind` 移行は **v1.2 送り**(現状はハードコード、テーマだけ反映される)。
- asciinema demo の `.cast` ファイルは未収録。録画手順は `cli/asciinema/README.md` 参照。

---

## 7. テストが失敗したときの基本

- ビルドエラー → `npm run typecheck` でメッセージ確認
- 依存問題 → `rm -rf node_modules package-lock.json && npm install`
- LFS ファイル smudge エラー(`csv/similar_audit_findings.csv` 等)→ `git update-index --skip-worktree csv/similar_audit_findings.csv`
- Windows で行末問題 → `git config core.autocrlf false` で再 checkout
- それでも直らなければ Issue 起票

---

## まとめ(最低限これだけ通れば OK)

```bash
npm test                                # 1. ユニット 220/220
node dist/cli.js doctor                 # 2. インストール環境健全性
node dist/cli.js init --non-interactive --target-repo URL --target-language Rust --target-layer consensus --rubric default --output-dir TMP --yes  # 3. 設定生成
node dist/cli.js run --phase 01b --json # 4. NDJSON pass-through
node dist/cli.js browse FIXTURE --no-tui  # 5. 検出結果ブラウザ
```

これで CI 通過 + smoke 完走相当。
