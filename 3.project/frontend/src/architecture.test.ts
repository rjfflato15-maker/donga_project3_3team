/// <reference types="vite/client" />
import ts from 'typescript';
import { expect, it } from 'vitest';

const sources = new Map(Object.entries(import.meta.glob<string>('./**/*.{ts,tsx}', { eager: true, query: '?raw', import: 'default' })).filter(([file]) => !/\.test\./.test(file)));
const files = [...sources.keys()];
const relative = (file: string) => file.replace(/^\.\//, '');
const imports = (file: string, runtime = false) => {
  const source = sources.get(file)!;
  const text = runtime ? ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText : source;
  const ast = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  return ast.statements.flatMap(node => (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier) ? [node.moduleSpecifier.text] : []);
};
const resolve = (file: string, specifier: string) => {
  const parts = file.split('/').slice(0, -1);
  for (const part of specifier.split('/')) { if (part === '..') parts.pop(); else if (part !== '.') parts.push(part); }
  const base = parts.join('/');
  return [base, `${base}.ts`, `${base}.tsx`, `${base}/index.ts`].find(candidate => sources.has(candidate));
};
const graph = new Map(files.map(file => [file, imports(file, true).filter(specifier => specifier.startsWith('.')).flatMap(specifier => resolve(file, specifier) ?? [])]));

it('all relative TypeScript imports resolve after retired modules are removed', () => {
  const missing = files.flatMap(file => imports(file).filter(specifier => specifier.startsWith('.') && !/\.css$/.test(specifier) && !resolve(file, specifier)).map(specifier => `${relative(file)} -> ${specifier}`));
  expect(missing).toEqual([]);
});

it('runtime imports have no component cycles', () => {
  const completed = new Set<string>(); const stack: string[] = []; const cycles: string[][] = [];
  const visit = (file: string) => {
    const index = stack.indexOf(file);
    if (index >= 0) { cycles.push([...stack.slice(index), file].map(relative)); return; }
    if (completed.has(file)) return;
    stack.push(file); graph.get(file)?.forEach(visit); stack.pop(); completed.add(file);
  };
  files.forEach(visit);
  expect(cycles).toEqual([]);
});

it('shared feature contracts and APIs never depend on screen components or React', () => {
  const leaks = files.filter(file => relative(file).startsWith('features/')).flatMap(file => imports(file).filter(specifier => specifier === 'react' || /(?:components|pages|hooks)\//.test(specifier)).map(specifier => `${relative(file)} -> ${specifier}`));
  expect(leaks).toEqual([]);
});

it('both pilot workspaces and demo screens remain reachable from the application entry', () => {
  const reached = new Set<string>();
  const visit = (file: string) => { if (reached.has(file)) return; reached.add(file); graph.get(file)?.forEach(visit); };
  visit('./main.tsx');
  const names = [...reached].map(relative);
  for (const file of [
    'components/review/ContractStageView.tsx', 'components/review/DocumentWorkspace.tsx',
    'components/review/StageDashboard.tsx', 'components/review/ContractSearch.tsx',
    'components/review/ApprovalPanel.tsx', 'components/review/AssignmentPanel.tsx',
    'components/PilotPasswordChange.tsx', 'components/PilotOperations.tsx',
    'components/OverallDashboardView.tsx', 'components/ContractsListView.tsx',
    'components/review/ContractReviewOverview.tsx', 'components/DocumentViewerModal.tsx',
  ]) expect(names).toContain(file);
});

it('retired screens and retired email-reset endpoints cannot re-enter the frontend', () => {
  const retired = ['Checklist', 'DocumentsView', 'MetricsSummary', 'Navbar', 'PipelineSimulator', 'TopHeader', 'PilotReviewPanel', 'PilotDocumentDialog', 'VlmRereadPanel', 'AccountPasswordResetView'];
  expect(files.filter(file => retired.includes(file.split('/').pop()!.replace(/\.tsx$/, ''))).map(relative)).toEqual([]);
  expect([...sources.values()].some(source => /['"`]\/api\/auth\/(send-verification-code|verify-code|change-password)/.test(source) || /['"`]\/send-verification-code['"`]|['"`]\/verify-code['"`]|['"`]\/change-password['"`]/.test(source))).toBe(false);
});
