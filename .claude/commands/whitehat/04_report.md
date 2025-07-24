# WHITEHAT 04 REPORT - Bug Bountyレポート生成

Ethereum Foundation向けのBug Bountyレポートを生成します。

Usage: `/04_report <vuln_name> <poc_test_file>`
Example: `/04_report DoSUnboundedImport crates/net/network/src/transactions/mod.rs crates/net/network/src/transactions/it_poc_dos_unbounded_import.rs`

Arguments:
- vuln_name: 脆弱性名
- poc_test_file: PoCテストファイルパス

---

<% 
// Parse arguments with support for quoted strings
const args = input.trim().match(/(?:[^\s"]+|"[^"]*")+/g) || [];
const vulnName = args[0] || 'DoSUnboundedImport';
const pocTestFile = args[3] || 'crates/net/network/src/transactions/it_poc_dos_unbounded_import.rs';

// Read the original prompt content
const fs = require('fs');
const promptContent = fs.readFileSync('prompts/whitehat/04_REPORT.md', 'utf8');

// Replace template variables
const processedContent = promptContent
  .replace(/\{\{VULN_NAME\}\}/g, vulnName)
  .replace(/\{\{POC_TEST_FILE\}\}/g, pocTestFile)

%>

<%= processedContent %>
