# WHITEHAT 04 REPORT - Bug Bountyレポート生成

Ethereum Foundation向けのBug Bountyレポートを生成します。

Usage: `/04_report <vuln_name> <snippet> <vuln_file_line> <poc_test_file> [template] [bounty_url]`
Example: `/04_report DoSUnboundedImport "fn import_transactions(" crates/net/network/src/transactions/mod.rs crates/net/network/src/transactions/it_poc_dos_unbounded_import.rs`

Arguments:
- vuln_name: 脆弱性名
- snippet: コードスニペット
- vuln_file_line: 脆弱性ファイルパスと行番号
- poc_test_file: PoCテストファイルパス
- template: レポートテンプレート（省略時: security-agent/docs/report_templete_ethereum.md）
- bounty_url: バウンティページURL（省略時: https://ethereum.org/en/bug-bounty/）

---

<% 
// Parse arguments with support for quoted strings
const args = input.trim().match(/(?:[^\s"]+|"[^"]*")+/g) || [];
const vulnName = args[0] || 'DoSUnboundedImport';
const snippet = args[1] ? args[1].replace(/"/g, '') : 'fn import_transactions(';
const vulnFileLine = args[2] || 'crates/net/network/src/transactions/mod.rs';
const pocTestFile = args[3] || 'crates/net/network/src/transactions/it_poc_dos_unbounded_import.rs';
const template = args[4] || 'security-agent/docs/report_templete_ethereum.md';
const bountyUrl = args[5] || 'https://ethereum.org/en/bug-bounty/';

// Read the original prompt content
const fs = require('fs');
const promptContent = fs.readFileSync('prompts/whitehat/04_REPORT.md', 'utf8');

// Replace template variables
const processedContent = promptContent
  .replace(/\{\{REPORT_TEMPLATE\}\}/g, template)
  .replace(/\{\{BOUNTY_PAGE_URL\}\}/g, bountyUrl)
  .replace(/\{\{VULN_NAME\}\}/g, vulnName)
  .replace(/\{\{SNIPPET\}\}/g, snippet)
  .replace(/\{\{VULN_FILE_LINE\}\}/g, vulnFileLine)
  .replace(/\{\{POC_TEST_FILE\}\}/g, pocTestFile)
  .replace(/\{\{Poc_TEST_FILE\}\}/g, pocTestFile);
%>

<%= processedContent %>