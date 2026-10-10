import json
from pathlib import Path
import tempfile
import unittest

from tools.docs.lint_docs import anchors, destinations, erd_block, inspect_document, lint


class DocLintTests(unittest.TestCase):
    def test_code_examples_are_not_links_and_reference_links_are_checked(self):
        text = '[real](<space name.md>)\n`[example](missing.md)`\n```md\n[example](missing.md)\n```\n[ref][id]\n[id]: target.md\n'
        self.assertEqual([target for _, target in destinations(text)], ['space name.md', 'target.md'])

    def test_korean_duplicate_and_inline_code_heading_anchors(self):
        found = anchors('# 실행 · `설정`\n## 실행 · `설정`\n```\n# not-a-heading\n```')
        self.assertEqual(found, {'실행--설정', '실행--설정-1'})

    def test_missing_files_anchors_and_repository_escape_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'target.md').write_text('# 확인\n', encoding='utf-8')
            page = root / 'README.md'
            page.write_text('[a](target.md#없는-제목)\n[b](missing.md)\n[c](../private.md)\n', encoding='utf-8')
            issues, _ = inspect_document(page, root)
            self.assertEqual({item['code'] for item in issues}, {'MISSING_ANCHOR', 'MISSING_TARGET', 'OUTSIDE_REPOSITORY'})

    def test_external_urls_are_not_fetched_and_encoded_paths_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '한 글.md').write_text('# 확인\n', encoding='utf-8')
            page = root / 'README.md'
            page.write_text('[a](%ED%95%9C%20%EA%B8%80.md#확인)\n[a](https://example.invalid/)\n', encoding='utf-8')
            self.assertEqual(inspect_document(page, root)[0], [])

    def test_orphaned_doc_and_duplicate_canonical_owner_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('README.md', 'orphan.md'):
                (root / name).write_text('# 문서\n\n> 상태: 현재 기준\n> 확인일: 오늘\n> 기준: 작업 트리\n', encoding='utf-8')
            policy = {'entrypoints': ['README.md'], 'documents': [
                {'path': name, 'status': 'current', 'canonical_for': ['one-owner']} for name in ('README.md', 'orphan.md')]}
            errors = lint(root, policy)['errors']
            self.assertEqual({item['code'] for item in errors}, {'UNREACHABLE_DOCUMENT', 'DUPLICATE_OWNER'})

    def test_missing_metadata_source_and_changed_code_contract_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'README.md').write_text('# 문서\n', encoding='utf-8')
            (root / 'config.py').write_text('INTERVAL = 20\n', encoding='utf-8')
            policy = {'entrypoints': ['README.md'], 'documents': [
                {'path': 'README.md', 'status': 'current', 'sources': ['missing.py']}],
                'code_contracts': [{'name': '기록된 간격', 'source': 'config.py',
                    'pattern': r'INTERVAL = 10', 'document': 'README.md'}]}
            self.assertEqual({item['code'] for item in lint(root, policy)['errors']},
                             {'MISSING_METADATA', 'MISSING_SOURCE', 'CODE_CONTRACT_CHANGED'})

    def test_erd_drift_is_detected_without_importing_models(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'backend/app/db/models.py'
            source.parent.mkdir(parents=True)
            source.write_text("raise RuntimeError('must never import')\nclass Parent(Base):\n"
                "    __tablename__ = 'parents'\n    id = Column(Integer, primary_key=True)\n"
                "class Child(Base):\n    __tablename__ = 'children'\n"
                "    id = Column(Integer, primary_key=True)\n"
                "    parent_id = Column(Integer, ForeignKey('parents.id'), nullable=True)\n", encoding='utf-8')
            diagram = erd_block(root)
            self.assertIn('parents |o..o{ children', diagram)
            page = root / 'README.md'
            page.write_text('# 문서\n\n> 상태: 현재 기준\n> 확인일: 오늘\n> 기준: 코드\n\n' + diagram, encoding='utf-8')
            policy = {'entrypoints': ['README.md'], 'documents': [{'path': 'README.md', 'status': 'current'}],
                      'erd_document': 'README.md'}
            self.assertEqual(lint(root, policy)['errors'], [])
            source.write_text(source.read_text() + '    note = Column(Text)\n', encoding='utf-8')
            self.assertIn('ERD_OUTDATED', {item['code'] for item in lint(root, policy)['errors']})


if __name__ == '__main__':
    unittest.main()
