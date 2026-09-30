const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.resolve(__dirname, '..');
const frontendDir = path.join(rootDir, 'frontend');

// 1. Detect Python executable
function getPythonExecutable() {
  const isWin = process.platform === 'win32';
  const venvPythonWin = path.join(rootDir, 'backend', '.venv', 'Scripts', 'python.exe');
  const venvPythonUnix = path.join(rootDir, 'backend', '.venv', 'bin', 'python');

  if (fs.existsSync(venvPythonWin)) {
    return venvPythonWin;
  }
  if (fs.existsSync(venvPythonUnix)) {
    return venvPythonUnix;
  }

  // Fallback to system python
  try {
    const testCmd = isWin ? 'where python' : 'which python3 || which python';
    const result = execSync(testCmd, { encoding: 'utf-8' }).trim().split(/\r?\n/)[0];
    if (result) return result;
  } catch (e) {}

  return isWin ? 'python' : 'python3';
}

// 2. Detect npm executable
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const pythonExe = getPythonExecutable();

console.log('\x1b[1m\x1b[36m=====================================================\x1b[0m');
console.log('\x1b[1m\x1b[32m🚀 Starting AI Contract Evidence Manager (Dev Mode)\x1b[0m');
console.log('\x1b[90mBackend Python:\x1b[0m', pythonExe);
console.log('\x1b[90mFrontend Manager:\x1b[0m', npmCmd);
console.log('\x1b[1m\x1b[36m=====================================================\x1b[0m\n');

let backendProcess = null;
let frontendProcess = null;
let isShuttingDown = false;

function killProcess(proc) {
  if (!proc || !proc.pid) return;
  if (process.platform === 'win32') {
    try {
      execSync(`taskkill /pid ${proc.pid} /T /F >nul 2>&1`);
    } catch (e) {}
  } else {
    try {
      proc.kill('SIGINT');
    } catch (e) {}
  }
}

function cleanExit() {
  if (isShuttingDown) return;
  isShuttingDown = true;
  console.log('\n\x1b[33m🛑 Stopping all services...\x1b[0m');
  killProcess(backendProcess);
  killProcess(frontendProcess);
  process.exit(0);
}

process.on('SIGINT', cleanExit);
process.on('SIGTERM', cleanExit);
process.on('exit', cleanExit);

// 3. Start Backend
backendProcess = spawn(
  pythonExe,
  ['-m', 'uvicorn', 'backend.app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload'],
  { cwd: rootDir, shell: false, env: { ...process.env, PYTHONUNBUFFERED: '1' } }
);

backendProcess.stdout.on('data', (data) => {
  const lines = data.toString().split(/\r?\n/);
  for (const line of lines) {
    if (line.trim()) {
      console.log(`\x1b[34m[BACKEND]\x1b[0m ${line}`);
    }
  }
});

backendProcess.stderr.on('data', (data) => {
  const lines = data.toString().split(/\r?\n/);
  for (const line of lines) {
    if (line.trim()) {
      console.log(`\x1b[34m[BACKEND]\x1b[0m ${line}`);
    }
  }
});

backendProcess.on('close', (code) => {
  if (!isShuttingDown) {
    console.log(`\x1b[31m[BACKEND] Process exited with code ${code}\x1b[0m`);
    cleanExit();
  }
});

// 4. Start Frontend
frontendProcess = spawn(
  npmCmd,
  ['run', 'dev'],
  { cwd: frontendDir, shell: true }
);

frontendProcess.stdout.on('data', (data) => {
  const lines = data.toString().split(/\r?\n/);
  for (const line of lines) {
    if (line.trim()) {
      console.log(`\x1b[32m[FRONTEND]\x1b[0m ${line}`);
    }
  }
});

frontendProcess.stderr.on('data', (data) => {
  const lines = data.toString().split(/\r?\n/);
  for (const line of lines) {
    if (line.trim()) {
      console.log(`\x1b[32m[FRONTEND]\x1b[0m ${line}`);
    }
  }
});

frontendProcess.on('close', (code) => {
  if (!isShuttingDown) {
    console.log(`\x1b[31m[FRONTEND] Process exited with code ${code}\x1b[0m`);
    cleanExit();
  }
});

setTimeout(() => {
  if (!isShuttingDown) {
    console.log('\n\x1b[1m\x1b[32m✔ Services are running!\x1b[0m');
    console.log('  🌐 Frontend UI: \x1b[4m\x1b[36mhttp://localhost:5173\x1b[0m');
    console.log('  📖 Backend Docs: \x1b[4m\x1b[36mhttp://localhost:8000/docs\x1b[0m');
    console.log('  ⚡ Press \x1b[1mCtrl + C\x1b[0m to stop all services.\n');
  }
}, 2500);
