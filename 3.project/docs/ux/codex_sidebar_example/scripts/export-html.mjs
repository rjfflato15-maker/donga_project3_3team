import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
let html = readFileSync(resolve(root, 'dist/client/index.html'), 'utf8');
html = html.replace(/<script\b[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g, (_, url) => {
  const script = readFileSync(resolve(root, 'dist/client', url.replace(/^\//, '')), 'utf8');
  return `<script type="module">${script.replace(/<\/script/gi, '<\\/script')}</script>`;
});
html = html.replace(/<link\b[^>]*\bhref="([^"]+\.css)"[^>]*>/g, (_, url) => {
  return `<style>${readFileSync(resolve(root, 'dist/client', url.replace(/^\//, '')), 'utf8')}</style>`;
});
html = html.replace('</body>', '<noscript>이 클릭 시안은 JavaScript를 지원하는 브라우저에서 열어 주세요.</noscript></body>');
writeFileSync(resolve(root, 'codex-sidebar-example.html'), html);
console.log('Standalone HTML exported: codex-sidebar-example.html');
