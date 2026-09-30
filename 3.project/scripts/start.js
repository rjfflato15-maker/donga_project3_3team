const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.resolve(__dirname, '..');
const frontendDir = path.join(rootDir, 'frontend');
const distDir = path.join(frontendDir, 'dist');

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

const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const pythonExe = getPythonExecutable();

console.log('\x1b[1m\x1b[36m=====================================================\x1b[0m');
console.log('\x1b[1m\x1b[32m🚀 Starting Production Server (Single Port 8000)\x1b[0m');
console.log('\x1b[1m\x1b[36m=====================================================\x1b[0m\n');

// 1. Build frontend if dist doesn't exist
if (!fs.existsSync(path.join(distDir, 'index.html'))) {
  console.log('\x1b[33m📦 Frontend dist not found. Building frontend first...\x1b[0m');
  try {
    execSync(`${npmCmd} run build`, { cwd: frontendDir, stdio: 'inherit' });
    console.log('\x1b[32m✔ Frontend build complete!\x1b[0m\n');
  } catch (e) {
    console.error('\x1b[31m✖ Failed to build frontend:\x1b[0m', e.message);
    process.exit(1);
  }
}

console.log('\x1b[34m[SERVER]\x1b[0m Launching FastAPI unified server (serving API + Frontend SPA)...');

const server = spawn(
  pythonExe,
  ['-m', 'uvicorn', 'backend.app.main:app', '--host', '0.0.0.0', '--port', '8000'],
  { cwd: rootDir, stdio: 'inherit' }
);

server.on('close', (code) => {
  console.log(`Server stopped with code ${code}`);
  process.exit(code || 0);
});

process.on('SIGINT', () => {
  server.kill('SIGINT');
  process.exit(0);
});
