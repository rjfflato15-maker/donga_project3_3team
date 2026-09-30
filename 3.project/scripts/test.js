const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.resolve(__dirname, '..');

function getPythonExecutable() {
  const isWin = process.platform === 'win32';
  const venvPythonWin = path.join(rootDir, 'backend', '.venv', 'Scripts', 'python.exe');
  const venvPythonUnix = path.join(rootDir, 'backend', '.venv', 'bin', 'python');

  if (fs.existsSync(venvPythonWin)) return venvPythonWin;
  if (fs.existsSync(venvPythonUnix)) return venvPythonUnix;

  return isWin ? 'python' : 'python3';
}

const pythonExe = getPythonExecutable();
console.log(`Running pytest with: ${pythonExe}`);

const testProcess = spawn(
  pythonExe,
  ['-m', 'pytest', 'backend/tests', '-v'],
  { cwd: rootDir, stdio: 'inherit' }
);

testProcess.on('close', (code) => {
  process.exit(code || 0);
});
