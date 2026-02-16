#!/usr/bin/env python3
"""
コールグラフ解析スクリプト

Tree-sitter MCPを使ってエントリーポイントからコールグラフを構築し、
チェックリスト項目と実装コードをマッピングする。

使用方法:
    python3 scripts/build_callgraph.py \
        --target-workspace /path/to/target \
        --checklist outputs/02_PARTIAL_*.json \
        --output outputs/callgraph.json
"""

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict


@dataclass
class EntryPoint:
    """エントリーポイント情報"""
    name: str
    file: str
    line: int
    category: str
    confidence: float


@dataclass
class CallGraphNode:
    """コールグラフのノード"""
    function: str
    file: str
    line_start: int
    line_end: int
    calls: List[Dict[str, any]]


@dataclass
class CodeLocation:
    """コード位置情報"""
    file: str
    symbol: str
    line_range: Tuple[int, int]
    role: str  # "primary", "related", "caller"


def mcp_call(tool: str, server: str, args: Dict) -> Dict:
    """
    MCPツールを呼び出す
    """
    cmd = [
        "manus-mcp-cli",
        "tool",
        "call",
        tool,
        "--server",
        server,
        "--input",
        json.dumps(args)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"MCP call failed: {result.stderr}")
    
    return json.loads(result.stdout)


def register_project(workspace_path: str, project_name: str = "target-project"):
    """
    Tree-sitter MCPにプロジェクトを登録
    """
    print(f"Registering project: {workspace_path}")
    
    result = mcp_call(
        tool="register_project_tool",
        server="tree_sitter",
        args={
            "path": workspace_path,
            "name": project_name,
            "description": "Target project for security audit"
        }
    )
    
    print(f"Project registered: {result}")
    return project_name


def get_all_symbols(project_name: str) -> List[Dict]:
    """
    プロジェクト内の全シンボルを取得
    """
    print("Extracting all symbols...")
    
    # 全Goファイルを取得
    files_result = mcp_call(
        tool="list_files",
        server="tree_sitter",
        args={
            "project": project_name,
            "pattern": "**/*.go"
        }
    )
    
    go_files = files_result.get("files", [])
    print(f"Found {len(go_files)} Go files")
    
    all_symbols = []
    
    for file_path in go_files:
        try:
            symbols_result = mcp_call(
                tool="get_symbols",
                server="tree_sitter",
                args={
                    "project": project_name,
                    "file_path": file_path
                }
            )
            
            symbols = symbols_result.get("symbols", [])
            all_symbols.extend(symbols)
            
        except Exception as e:
            print(f"Warning: Failed to extract symbols from {file_path}: {e}")
            continue
    
    print(f"Extracted {len(all_symbols)} symbols")
    return all_symbols


# エントリーポイントパターン定義
ENTRY_POINT_PATTERNS = {
    "P2P": {
        "function_patterns": [
            r"Handle.*Message",
            r"Receive.*Block",
            r"Process.*Block",
            r"Validate.*Block",
            r"On.*Received",
            r"Sync.*"
        ],
        "file_patterns": [
            r".*/p2p/.*",
            r".*/sync/.*",
            r".*/network/.*"
        ]
    },
    "Transaction": {
        "function_patterns": [
            r"Process.*Transaction",
            r"Validate.*Transaction",
            r"Apply.*Transaction",
            r"Execute.*Transaction",
            r"Verify.*Signature",
            r"Recover.*Sender"
        ],
        "file_patterns": [
            r".*/txpool/.*",
            r".*/core/types/transaction.*",
            r".*/core/state_transition.*"
        ]
    },
    "EngineAPI": {
        "function_patterns": [
            r"Engine.*",
            r"ForkchoiceUpdated.*",
            r"NewPayload.*",
            r"GetPayload.*",
            r"ExchangeTransitionConfiguration.*"
        ],
        "file_patterns": [
            r".*/eth/catalyst/.*",
            r".*/beacon/engine/.*",
            r".*/miner/payload.*"
        ]
    },
    "Consensus": {
        "function_patterns": [
            r"VerifyHeader.*",
            r"VerifyHeaders.*",
            r"Prepare.*",
            r"Finalize.*",
            r"FinalizeAndAssemble.*",
            r"Seal.*"
        ],
        "file_patterns": [
            r".*/consensus/.*",
            r".*/core/headerchain.*"
        ]
    },
    "Internal": {
        "function_patterns": [
            r"process.*",
            r"apply.*",
            r"execute.*",
            r"transition.*"
        ],
        "file_patterns": [
            r".*/core/.*",
            r".*/internal/.*"
        ]
    }
}


def identify_entry_points(symbols: List[Dict], category: str) -> List[EntryPoint]:
    """
    シンボルリストからカテゴリに該当するエントリーポイントを特定
    """
    patterns = ENTRY_POINT_PATTERNS.get(category, {})
    func_patterns = patterns.get("function_patterns", [])
    file_patterns = patterns.get("file_patterns", [])
    
    entry_points = []
    
    for symbol in symbols:
        if symbol.get("kind") != "function":
            continue
        
        func_name = symbol.get("name", "")
        file_path = symbol.get("file", "")
        
        # 関数名でマッチング
        func_match = any(
            re.match(pattern, func_name) 
            for pattern in func_patterns
        )
        
        # ファイルパスでマッチング
        file_match = any(
            re.search(pattern, file_path) 
            for pattern in file_patterns
        )
        
        # どちらかにマッチすればエントリーポイント候補
        if func_match or file_match:
            confidence = 1.0 if (func_match and file_match) else 0.7
            
            entry_points.append(EntryPoint(
                name=func_name,
                file=file_path,
                line=symbol.get("line", 0),
                category=category,
                confidence=confidence
            ))
    
    return entry_points


def build_call_graph(
    project_name: str,
    entry_point: EntryPoint,
    max_depth: int = 5
) -> CallGraphNode:
    """
    エントリーポイントからコールグラフを構築
    """
    print(f"Building call graph for {entry_point.name}...")
    
    # Tree-sitterクエリでコールグラフを構築
    # Go言語の関数呼び出しパターン
    call_query = """
    (call_expression
      function: [
        (identifier) @call
        (selector_expression
          field: (field_identifier) @call)
      ])
    """
    
    visited: Set[str] = set()
    call_graph = CallGraphNode(
        function=entry_point.name,
        file=entry_point.file,
        line_start=entry_point.line,
        line_end=entry_point.line + 100,  # 推定
        calls=[]
    )
    
    def explore(func_name: str, file_path: str, depth: int):
        """深さ優先探索"""
        if depth >= max_depth or func_name in visited:
            return
        
        visited.add(func_name)
        
        try:
            # 関数内の呼び出しを抽出
            result = mcp_call(
                tool="run_query",
                server="tree_sitter",
                args={
                    "project": project_name,
                    "query": call_query,
                    "file_path": file_path,
                    "language": "go"
                }
            )
            
            matches = result.get("matches", [])
            
            for match in matches:
                called_func = match.get("text", "")
                call_line = match.get("line", 0)
                
                call_graph.calls.append({
                    "from": func_name,
                    "to": called_func,
                    "file": file_path,
                    "line": call_line,
                    "depth": depth
                })
                
                # 再帰的に探索（次の深さ）
                # Note: 呼び出された関数の定義を見つける必要があるが、
                # 簡略化のため、ここでは省略
                
        except Exception as e:
            print(f"Warning: Failed to explore {func_name}: {e}")
    
    explore(entry_point.name, entry_point.file, 0)
    
    return call_graph


def extract_keywords(test_procedure: str) -> List[str]:
    """
    test_procedureからキーワードを抽出
    """
    # 大文字の単語、snake_case、camelCaseを抽出
    keywords = []
    
    # 大文字の単語（例: RLP, MAX_RLP_BLOCK_SIZE）
    keywords.extend(re.findall(r'\b[A-Z_]{2,}\b', test_procedure))
    
    # snake_case（例: recover_sender, state_transition）
    keywords.extend(re.findall(r'\b[a-z]+_[a-z_]+\b', test_procedure))
    
    # camelCase（例: validateBlock, processTransaction）
    keywords.extend(re.findall(r'\b[a-z]+[A-Z][a-zA-Z]+\b', test_procedure))
    
    return list(set(keywords))


def map_checklist_to_code(
    checklist_item: Dict,
    entry_point_map: Dict[str, List[EntryPoint]],
    call_graphs: Dict[str, CallGraphNode]
) -> Dict:
    """
    チェックリスト項目をコードにマッピング
    """
    entry_points = checklist_item.get("reachability", {}).get("entry_points", [])
    test_procedure = checklist_item.get("test_procedure", "")
    
    # キーワード抽出
    keywords = extract_keywords(test_procedure)
    
    # 該当するコールグラフを取得
    relevant_calls = []
    for ep_category in entry_points:
        # カテゴリ正規化
        normalized_category = ep_category.replace(" ", "")
        if normalized_category == "EngineAPI":
            normalized_category = "EngineAPI"
        elif "Internal" in normalized_category:
            normalized_category = "Internal"
        
        eps = entry_point_map.get(normalized_category, [])
        
        for ep in eps:
            graph = call_graphs.get(ep.name)
            if graph:
                relevant_calls.extend(graph.calls)
    
    # キーワードマッチング
    matched_locations = []
    
    for call in relevant_calls:
        called_func = call["to"]
        
        # キーワードとの類似度計算
        relevance = sum(
            1 for kw in keywords 
            if kw.lower() in called_func.lower()
        ) / max(len(keywords), 1)
        
        if relevance > 0:
            matched_locations.append({
                "file": call["file"],
                "symbol": called_func,
                "line_range": [call["line"], call["line"] + 10],
                "role": "primary" if relevance > 0.5 else "related",
                "relevance": relevance
            })
    
    # 関連度でソート
    matched_locations.sort(key=lambda x: x["relevance"], reverse=True)
    
    return {
        "check_id": checklist_item.get("check_id"),
        "code_scope": {
            "locations": matched_locations[:5],  # Top 5
            "resolution_status": "resolved" if matched_locations else "not_found"
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Build call graph for security audit")
    parser.add_argument("--target-workspace", required=True, help="Path to target workspace")
    parser.add_argument("--checklist", required=True, help="Path to checklist JSON file")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum call graph depth")
    
    args = parser.parse_args()
    
    # 1. プロジェクト登録
    project_name = register_project(args.target_workspace)
    
    # 2. 全シンボル抽出
    all_symbols = get_all_symbols(project_name)
    
    # 3. エントリーポイント特定
    entry_point_map = {}
    for category in ["P2P", "Transaction", "EngineAPI", "Consensus", "Internal"]:
        entry_point_map[category] = identify_entry_points(all_symbols, category)
        print(f"{category}: {len(entry_point_map[category])} entry points")
    
    # 4. コールグラフ構築
    call_graphs = {}
    for category, eps in entry_point_map.items():
        for ep in eps[:10]:  # 各カテゴリTop 10のみ
            call_graphs[ep.name] = build_call_graph(project_name, ep, args.max_depth)
    
    # 5. チェックリスト読み込み
    with open(args.checklist, "r") as f:
        checklist_data = json.load(f)
    
    checklist = checklist_data.get("checklist", [])
    
    # 6. マッピング
    mapped_checklist = []
    for item in checklist:
        mapped = map_checklist_to_code(item, entry_point_map, call_graphs)
        mapped_checklist.append(mapped)
    
    # 7. 出力
    output_data = {
        "entry_points": {k: [asdict(ep) for ep in v] for k, v in entry_point_map.items()},
        "mapped_checklist": mapped_checklist
    }
    
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Call graph saved to {args.output}")


if __name__ == "__main__":
    main()
