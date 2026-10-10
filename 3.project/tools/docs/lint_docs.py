"""Dependency-free checks for maintained docs; historical records stay read-only.

Checks local links/anchors, document metadata, source references, navigation,
selected code contracts, and the generated ERD. Never executes doc commands or
fetches external URLs. --all reports historical/reference issues separately.
"""
import argparse
import ast
from collections import Counter
import html
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {'node_modules', '__pycache__', '.git', '.venv'}


def without_code(text):
    lines, fence = [], None
    for line in text.splitlines():
        opening = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(fence[1]) + r',}\s*$', line):
                fence = None
            lines.append('')
        elif opening:
            fence = (opening[1][0], len(opening[1]))
            lines.append('')
        else:
            lines.append(re.sub(r'(`+).*?\1', '', line))
    return '\n'.join(lines), fence is not None


def slug(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'!?\[([^]]*)\]\([^)]*\)', r'\1', text).replace('`', '')
    text = html.unescape(text).strip().lower()
    text = ''.join(c for c in text if c in '-_' or c.isspace() or unicodedata.category(c)[0] in {'L', 'N'})
    return re.sub(r'\s', '-', text)


def anchors(text, suffix='.md'):
    if suffix.lower() in {'.html', '.htm'}:
        return set(re.findall(r'\b(?:id|name)=[\"\']([^\"\']+)[\"\']', text))
    result, counts, fence = set(), Counter(), None
    for line in text.splitlines():
        token = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(fence[1]) + r',}\s*$', line):
                fence = None
            continue
        if token:
            fence = (token[1][0], len(token[1]))
            continue
        heading = re.match(r'^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?$', line)
        if heading:
            key = slug(heading[1])
            result.add(key if counts[key] == 0 else f'{key}-{counts[key]}')
            counts[key] += 1
    result.update(re.findall(r'\bid=[\"\']([^\"\']+)[\"\']', text))
    return result


def destinations(text):
    clean, _ = without_code(text)
    references = {re.sub(r'\s+', ' ', name).lower(): target for name, target in
        re.findall(r'^ {0,3}\[([^]\n]+)\]:\s*(<[^>]+>|\S+)', clean, re.M)}
    links = []
    for match in re.finditer(r'!?\[[^]\n]*\]\((<[^>]*>|[^\n)]*(?:\([^)]*\)[^\n)]*)*)\)', clean):
        target = match[1].strip()
        if target.startswith('<'):
            target = target[1:target.find('>')]
        else:
            target = re.split(r'\s+[\"\']', target, maxsplit=1)[0]
        links.append((clean.count('\n', 0, match.start()) + 1, target))
    for match in re.finditer(r'\[([^]\n]+)\]\[([^]\n]*)\]', clean):
        label = re.sub(r'\s+', ' ', match[2] or match[1]).lower()
        links.append((clean.count('\n', 0, match.start()) + 1, references.get(label, None)))
    for match in re.finditer(r'\b(?:href|src)=[\"\']([^\"\']+)[\"\']', clean):
        links.append((clean.count('\n', 0, match.start()) + 1, html.unescape(match[1])))
    return links


def local_target(document, destination, root):
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc:
        return None
    target = root / unquote(parsed.path).lstrip('/') if parsed.path.startswith('/') else document.parent / unquote(parsed.path)
    return target.resolve(), unquote(parsed.fragment)


def inspect_document(path, root):
    text = path.read_text(encoding='utf-8-sig')
    issues, targets = [], []
    _, unclosed = without_code(text)
    if unclosed:
        issues.append({'line': 1, 'code': 'UNCLOSED_FENCE', 'detail': '코드 블록이 닫히지 않았습니다.'})
    for line, destination in destinations(text):
        if destination is None:
            issues.append({'line': line, 'code': 'MISSING_REFERENCE', 'detail': '참조 링크 정의가 없습니다.'})
            continue
        resolved = local_target(path, destination, root)
        if resolved is None:
            continue
        target, fragment = resolved
        if not target.is_relative_to(root):
            issues.append({'line': line, 'code': 'OUTSIDE_REPOSITORY', 'detail': destination})
            continue
        if not target.exists():
            issues.append({'line': line, 'code': 'MISSING_TARGET', 'detail': destination})
            continue
        targets.append(target)
        if fragment:
            check_path = target / 'README.md' if target.is_dir() else target
            if check_path.suffix.lower() in {'.md', '.html', '.htm'} and check_path.is_file():
                if fragment not in anchors(check_path.read_text(encoding='utf-8-sig'), check_path.suffix):
                    issues.append({'line': line, 'code': 'MISSING_ANCHOR', 'detail': destination})
            elif re.fullmatch(r'L\d+(?:-L\d+)?', fragment) and check_path.is_file():
                limit = len(check_path.read_text(encoding='utf-8-sig').splitlines())
                if any(int(value) > limit for value in re.findall(r'\d+', fragment)):
                    issues.append({'line': line, 'code': 'MISSING_LINE', 'detail': destination})
    return issues, targets


def model_schema(root):
    """Parse declarations without importing config or connecting to a DB."""
    tree = ast.parse((root / 'backend/app/db/models.py').read_text(encoding='utf-8-sig'))
    tables = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        table, columns = None, []
        for assignment in node.body:
            if not isinstance(assignment, ast.Assign) or not isinstance(assignment.targets[0], ast.Name):
                continue
            name, value = assignment.targets[0].id, assignment.value
            if name == '__tablename__' and isinstance(value, ast.Constant):
                table = value.value
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != 'Column':
                continue
            type_node = value.args[0]
            kind = type_node.id if isinstance(type_node, ast.Name) else type_node.func.id
            flags = {item.arg: item.value.value for item in value.keywords if isinstance(item.value, ast.Constant)}
            foreign = [item.args[0].value for item in value.args if isinstance(item, ast.Call)
                       and isinstance(item.func, ast.Name) and item.func.id == 'ForeignKey']
            columns.append({'name': name, 'type': kind, 'pk': flags.get('primary_key', False),
                            'unique': flags.get('unique', False), 'foreign': foreign,
                            'nullable': flags.get('nullable', not flags.get('primary_key', False))})
        if table:
            tables[table] = columns
    return tables


def erd_block(root):
    tables = model_schema(root)
    lines = ['```mermaid', 'erDiagram']
    for table, columns in tables.items():
        lines.append(f'    {table} {{')
        for column in columns:
            keys = [key for key, yes in [('PK', column['pk']), ('FK', bool(column['foreign'])), ('UK', column['unique'])] if yes]
            lines.append(f"        {column['type']} {column['name']}" + (' ' + ','.join(keys) if keys else ''))
        lines.append('    }')
    for table, columns in tables.items():
        for column in columns:
            for foreign in column['foreign']:
                parent = foreign.split('.')[0]
                left = '|o' if column['nullable'] else '||'
                right = 'o|' if column['pk'] or column['unique'] else 'o{'
                connector = '--' if column['pk'] else '..'
                lines.append(f'    {parent} {left}{connector}{right} {table} : "{column["name"]}"')
    lines.append('```')
    return '\n'.join(lines)


def lint(root, policy, all_docs=False):
    errors, historical, graph = [], [], {}
    link_root = root.parent if policy.get('workspace_root_is_parent') else root
    documents = policy['documents']
    known = {record['path'] for record in documents}
    if len(known) != len(documents):
        errors.append({'path': 'docs/documentation_manifest.json', 'code': 'DUPLICATE_DOCUMENT'})
    owners = Counter(key for record in documents for key in record.get('canonical_for', []))
    for key, count in owners.items():
        if count != 1:
            errors.append({'path': 'docs/documentation_manifest.json', 'code': 'DUPLICATE_OWNER', 'detail': key})
    for record in documents:
        path = root / record['path']
        if not path.is_file():
            errors.append({'path': record['path'], 'code': 'MISSING_DOCUMENT'})
            continue
        text = path.read_text(encoding='utf-8-sig')
        if record['status'] not in {'current', 'draft', 'record'}:
            errors.append({'path': record['path'], 'code': 'INVALID_STATUS'})
        for marker in ('> 상태:', '> 확인일:', '> 기준:'):
            if marker not in text[:2500]:
                errors.append({'path': record['path'], 'code': 'MISSING_METADATA', 'detail': marker})
        for source in record.get('sources', []):
            if not (root / source).exists():
                errors.append({'path': record['path'], 'code': 'MISSING_SOURCE', 'detail': source})
        findings, links = inspect_document(path, link_root)
        errors.extend({'path': record['path'], **item} for item in findings)
        graph[path.resolve()] = links
    reachable, pending = set(), [root / name for name in policy['entrypoints']]
    while pending:
        path = pending.pop().resolve()
        if path in reachable:
            continue
        reachable.add(path)
        pending.extend(graph.get(path, []))
    for record in documents:
        if (root / record['path']).resolve() not in reachable:
            errors.append({'path': record['path'], 'code': 'UNREACHABLE_DOCUMENT'})
    for contract in policy.get('code_contracts', []):
        path = root / contract['source']
        if not path.exists() or re.search(contract['pattern'], path.read_text(encoding='utf-8-sig')) is None:
            errors.append({'path': contract['document'], 'code': 'CODE_CONTRACT_CHANGED', 'detail': contract['name']})
    if policy.get('erd_document'):
        path = root / policy['erd_document']
        if not path.exists() or erd_block(root) not in path.read_text(encoding='utf-8-sig'):
            errors.append({'path': policy['erd_document'], 'code': 'ERD_OUTDATED'})
    if all_docs:
        for path in sorted((root / 'docs').rglob('*.md')):
            name = path.relative_to(root).as_posix()
            if name in known or any(part in SKIP_DIRS for part in path.parts):
                continue
            findings, _ = inspect_document(path, link_root)
            historical.extend({'path': name, **item} for item in findings)
    return {'maintained_documents': len(documents), 'errors': errors, 'historical_reference_findings': historical}


def main():
    parser = argparse.ArgumentParser(description='현재 문서의 링크·출처·탐색·코드 기준 검사')
    parser.add_argument('--all', action='store_true', help='보존 문서의 링크 문제를 별도로 보고')
    parser.add_argument('--report', type=Path, help='JSON 결과 저장 경로')
    args = parser.parse_args()
    policy = json.loads((ROOT / 'docs/documentation_manifest.json').read_text(encoding='utf-8'))
    result = lint(ROOT, policy, args.all)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Maintained docs: {result['maintained_documents']} | errors: {len(result['errors'])} | historical/reference findings: {len(result['historical_reference_findings'])}")
    for item in result['errors'][:30]:
        print(f"{item['path']}:{item.get('line', 1)} {item['code']} {item.get('detail', '')}")
    if result['historical_reference_findings']:
        print('Historical/reference files were not modified; use --report for the complete list.')
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
