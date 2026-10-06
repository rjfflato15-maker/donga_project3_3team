const fs=require('node:fs');const postcss=require('postcss');
const base='../docs/ux/codex_sidebar_example/src/';
const css=postcss.parse(fs.readFileSync(base+'prototype.css','utf8')+'\n'+fs.readFileSync(base+'story.css','utf8'));
css.walkRules(rule=>{if(rule.parent?.type==='atrule'&&/keyframes/.test(rule.parent.name))return;rule.selectors=rule.selectors.map(s=>{s=s.trim();if(s===':root'||s==='body')return '.cf-app';if(/^(\.story-app|\.app|\.nav-open|\.nav-closed)(\b|[ .:#])/.test(s))return s.replace(/^(\.[\w-]+)/,'.cf-app$1');return '.cf-app '+s;});});
fs.writeFileSync('src/compare-ui.css','/* Canonical: approved ui_compare.html right-hand StoryPreview. Scoped original CSS. */\n'+css.toString());
