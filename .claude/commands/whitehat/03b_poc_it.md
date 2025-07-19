# WHITEHAT 03b POC INTEGRATION - 統合テストPoC生成

脆弱性を再現する統合レベルのPoCテストを作成します。

Usage: `/03b_poc_it <unit_test_poc> <it_test_path> <vuln_name>`
Example: `/03b_poc_it crates/net/network/src/transactions/poc_dos_unbounded_import.rs crates/net/network/tests/it/poc_tx_import.rs DoSUnboundedImport`

Arguments:
- unit_test_poc: ユニットテストPoCファイルパス
- it_test_path: 統合テストファイルパス
- vuln_name: 脆弱性名

---

<% 
// Parse arguments
const args = input.trim().split(/\s+/);
const unitTestPoc = args[0] || 'crates/net/network/src/transactions/poc_dos_unbounded_import.rs';
const itTestPath = args[1] || 'crates/net/network/tests/it/poc_tx_import.rs';
const vulnName = args[2] || 'DoSUnboundedImport';

// Read the original prompt content
const fs = require('fs');
const promptContent = fs.readFileSync('prompts/whitehat/03b_POC_INTEGRATION.md', 'utf8');

// Replace template variables
const processedContent = promptContent
  .replace(/\{\{UNIT_TEST_POC\}\}/g, unitTestPoc)
  .replace(/\{\{IT_TEST_PATH\}\}/g, itTestPath)
  .replace(/\{\{VULN_NAME\}\}/g, vulnName);
%>

<%= processedContent %>