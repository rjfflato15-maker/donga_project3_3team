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

  try {
    const testCmd = isWin ? 'where python' : 'which python3 || which python';
    const result = execSync(testCmd, { encoding: 'utf-8' }).trim().split(/\r?\n/)[0];
    if (result) return result;
  } catch (e) {}

  return isWin ? 'python' : 'python3';
}

const pythonExe = getPythonExecutable();
console.log(`Starting Backend using: ${pythonExe}`);

const backend = spawn(
  pythonExe,
  ['-m', 'uvicorn', 'backend.app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload'],
  { cwd: rootDir, stdio: 'inherit' }
);

backend.on('close', (code) => {
  process.exit(code || 0);
});

process.on('SIGINT', () => {
  backend.kill('SIGINT');
  process.exit(0);
});
