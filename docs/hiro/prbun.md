# Pull Request: bug/fix-1

## タイトル

**fix: kijaku.md記載の12件のバグ修正（ORC/SCH/CI/BEN）**

## 概要

`docs/hiro/kijaku.md` に記載されたバグのうち、機械的に修正可能かつ影響度の高い12件を修正しました。全231テストがパスしています。

## 変更内容

### Orchestrator（5件）

| Bug ID | 重要度 | 内容 | 対象ファイル |
|--------|--------|------|-------------|
| BUG-ORC01 | High | `sys.exit()` を `PhaseAbortError` 例外に置換。プロセス強制終了を防ぎ、正常な例外処理フローを実現 | `scripts/orchestrator/base.py`, `scripts/orchestrator/__init__.py`, `scripts/run_phase.py` |
| BUG-ORC03 | High | `resume.py` の正規表現が大文字のみマッチし、小文字ディレクトリ名（`batch_w1b2_...`）を見逃す問題を修正。`re.IGNORECASE` + `.upper()` 追加 | `scripts/orchestrator/resume.py` |
| BUG-ORC05 | Medium | Phase04 `load_items` でリスト結合時に `property_id` 重複が発生する問題を dict ベースの重複排除に修正 | `scripts/orchestrator/base.py` |
| BUG-ORC12 | Low | 存在しない phase `"02"` の dead code ブロックを削除 | `scripts/orchestrator/runner.py` |

### Schema/Config（4件）

| Bug ID | 重要度 | 内容 | 対象ファイル |
|--------|--------|------|-------------|
| BUG-SCH01 | High | `AuditClassification` enum に Phase 03 が出力する4つの分類値（`VULNERABILITY`, `NOT_A_VULNERABILITY`, `POTENTIAL_VULNERABILITY`, `INFORMATIONAL`）を追加 | `scripts/orchestrator/schemas.py` |
| BUG-SCH03 | Medium | Phase 02c の `output_fields` に `code_excerpt` を追加。Phase 03 が `context_fields` で参照するフィールドの欠損を解消 | `scripts/orchestrator/config.py` |
| BUG-SCH04 | Low | `Severity` docstring の比較方向を修正（`CRITICAL < HIGH` → `CRITICAL > HIGH`） | `scripts/orchestrator/schemas.py` |
| BUG-SCH05/06 | Medium | テストのフィールド名を実際のスキーマに合わせて修正（`affected_boundary` → `trust_boundary_id`, `trust_assumptions/description` → `assumptions/text`） | `tests/test_schemas_and_config.py` |

### CI/CD（3件）

| Bug ID | 重要度 | 内容 | 対象ファイル |
|--------|--------|------|-------------|
| BUG-CI01 | High | 01e workflow で heredoc 内のインデント付き JSON が壊れる問題を `printf` 方式に修正 | `.github/workflows/01e-properties.yml` |
| BUG-CI02 | Medium | RQ1 benchmark workflow で git commit 前に `user.name`/`user.email` が未設定だった問題を修正 | `.github/workflows/benchmark-rq1-sherlock-eval.yml` |
| BUG-CI03 | Medium | `actions/upload-artifact@v6`（存在しない）を `@v4` に修正 | `.github/workflows/openhands-resolver.yml` |

### Benchmark（1件）

| Bug ID | 重要度 | 内容 | 対象ファイル |
|--------|--------|------|-------------|
| BUG-BEN01 | High | `collect_branch_outputs.py` の `ROOT_DIR` が `parents[1]`（`benchmarks/`）を指していた問題を `parents[2]`（プロジェクトルート）に修正 | `benchmarks/scripts/collect_branch_outputs.py` |

## テスト結果

```
231 passed in 5.15s
```

- 既存テスト全件パス
- リグレッションなし
- 新規追加した enum 値のアサーションも含む

## 変更ファイル一覧（12ファイル）

```
.github/workflows/01e-properties.yml
.github/workflows/benchmark-rq1-sherlock-eval.yml
.github/workflows/openhands-resolver.yml
benchmarks/scripts/collect_branch_outputs.py
scripts/orchestrator/__init__.py
scripts/orchestrator/base.py
scripts/orchestrator/config.py
scripts/orchestrator/resume.py
scripts/orchestrator/runner.py
scripts/orchestrator/schemas.py
scripts/run_phase.py
tests/test_schemas_and_config.py
```

## 未対応のバグ（今後の対応候補）

kijaku.md には合計84件のバグが記載されています。本PRでは12件を対応しました。残りの主要な未対応項目：

- **SEC-C01〜C04**（Critical セキュリティ脆弱性4件）：別PR で対応済み
- **BUG-ORC02, ORC04, ORC06〜ORC11**：Orchestrator の非同期処理・ロック・リトライ関連
- **BUG-SCH02, SCH07〜SCH10**：スキーマ検証強化
- **BUG-CI04〜CI06**：CI/CD 追加改善
- **BUG-BEN02〜BEN05**：ベンチマーク改善

## レビュー観点

1. `PhaseAbortError` の導入により `sys.exit()` が全て例外に置換されたこと
2. `resume.py` の正規表現修正が既存のレジューム動作に影響しないこと
3. Phase04 の dict ベース重複排除で `property_id` がキーとして適切であること
4. CI workflow の変更が各環境で正しく動作すること
