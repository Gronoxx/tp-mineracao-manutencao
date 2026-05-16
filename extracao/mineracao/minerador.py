import json
import hashlib
from pathlib import Path
from pydriller import Repository
from .ast_utils import parse_file_from_string
import ast

# (Di Nucci 2018, Beyazit 2026)
SMELL_KEYWORDS = {
    "long_method": [
        "extract method", "extract function", "split method", "split function",
        "refactor", "decompose", "break down", "too long", "large method"
    ],
    "long_param_list": [
        "parameter object", "introduce parameter", "too many params",
        "too many arguments", "reduce params", "refactor params"
    ],
    "magic_numbers": [
        "magic number", "named constant", "replace literal", "extract constant",
        "hardcoded", "magic string"
    ],
    "deep_nesting": [
        "guard clause", "early return", "reduce nesting", "flatten",
        "nested if", "deep nesting", "simplify condition"
    ],
    "dead_code": [
        "remove dead code", "dead code", "unused variable", "unreachable",
        "remove unused", "cleanup", "clean up"
    ],
}

MAP_SMELLS = { # mapeamento para gerar o rotulo automaticamente
    "long_method":      [1,0,0,0,0],
    "long_param_list":  [0,1,0,0,0],
    "magic_numbers":    [0,0,1,0,0],
    "deep_nesting":     [0,0,0,1,0],
    "dead_code":        [0,0,0,0,1],
}

def match_smells(commit_msg: str) -> list[str]:
    msg = commit_msg.lower()
    return [
        smell for smell, keywords in SMELL_KEYWORDS.items()
        if any(kw in msg for kw in keywords)
    ]

def is_valid_pair(before: str, after: str) -> bool:
    try:
        ast.parse(before)
        ast.parse(after)
    except SyntaxError:
        return False
    
    if before.strip() == after.strip():
        return False
    
    if len(after.strip()) < 10:
        return False
    
    return True

def extract_pairs(before_src: str, after_src: str, filename: str) -> list[dict]:
    """Retorna pares (before, after) para funções que mudaram."""
    try:
        before = parse_file_from_string(before_src, filename)
        after  = parse_file_from_string(after_src,  filename)
    except SyntaxError:
        return []  # arquivo com syntax error — descarta

    # índice por nome
    before_funcs = {f.name: f for f in before["functions"]}
    after_funcs  = {f.name: f for f in after["functions"]}

    # métodos também
    for cls in before["classes"]:
        for m in cls.methods:
            before_funcs[f"{cls.name}.{m.name}"] = m
            
    for cls in after["classes"]:
        for m in cls.methods:
            after_funcs[f"{cls.name}.{m.name}"] = m

    pairs = []
    for name, bf in before_funcs.items():
        if name in after_funcs and bf.source != after_funcs[name].source:
            
            if not is_valid_pair(bf.source, after_funcs[name].source):
                continue
            
            pairs.append({
                "name": name,
                "before": bf.source,
                "after": after_funcs[name].source,
            })
            
    return pairs

def mine(repo_url: str, output_path: Path, since=None, to=None):
    output_path.mkdir(parents=True, exist_ok=True)

    for commit in Repository(repo_url, since=since, to=to).traverse_commits():
        smells = match_smells(commit.msg)
        if not smells:
            continue

        for mf in commit.modified_files:
            
            if not mf.filename.endswith(".py"):
                continue
            
            if mf.source_code_before is None or mf.source_code is None:
                continue

            pairs = extract_pairs(mf.source_code_before, mf.source_code, mf.filename)

            for pair in pairs:
                for smell in smells:
                    record = {
                        "smell": smell,
                        "repo": repo_url,
                        "commit": commit.hash,
                        "file": mf.filename,
                        "name": pair["name"],
                        "before": pair["before"],
                        "after": pair["after"],
                        "y": MAP_SMELLS.get(smell)
                    }
                    # um arquivo JSONL por smell
                    out_file = output_path / f"{smell}.jsonl"
                    with open(out_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")