const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.resolve(__dirname, '..');
const frontendDir = path.join(rootDir, 'frontend');
const isWin = process.platform === 'win32';
const npmCmd = isWin ? 'npm.cmd' : 'npm';

console.log('\x1b[1m\x1b[36m=====================================================\x1b[0m');
console.log('\x1b[1m\x1b[32m🔧 Full Environment Setup (Backend + Frontend)\x1b[0m');
console.log('\x1b[1m\x1b[36m=====================================================\x1b[0m\n');

// 1. Python virtual environment setup
const venvDir = path.join(rootDir, 'backend', '.venv');
const venvPython = isWin
  ? path.join(venvDir, 'Scripts', 'python.exe')
  : path.join(venvDir, 'bin', 'python');

if (!fs.existsSync(venvPython)) {
  console.log('\x1b[33m🐍 Creating Python virtual environment in backend/.venv...\x1b[0m');
  try {
    execSync('python -m venv backend/.venv', { cwd: rootDir, stdio: 'inherit' });
    console.log('\x1b[32m✔ Python virtual environment created.\x1b[0m\n');
  } catch (err) {
    console.warn('\x1b[33m⚠️ Could not run "python -m venv", trying "python3 -m venv"...\x1b[0m');
    try {
      execSync('python3 -m venv backend/.venv', { cwd: rootDir, stdio: 'inherit' });
    } catch (e) {
      console.error('\x1b[31m✖ Failed to create virtual environment:\x1b[0m', e.message);
    }
  }
} else {
  console.log('\x1b[32m✔ Python virtual environment already exists at backend/.venv\x1b[0m\n');
}

// 2. Install Backend Requirements
const reqFile = path.join(rootDir, 'requirements.txt');
if (fs.existsSync(reqFile) && fs.existsSync(venvPython)) {
  console.log('\x1b[33m📦 Installing Backend dependencies from requirements.txt...\x1b[0m');
  try {
    execSync(`"${venvPython}" -m pip install --upgrade pip`, { cwd: rootDir, stdio: 'inherit' });
    execSync(`"${venvPython}" -m pip install -r requirements.txt`, { cwd: rootDir, stdio: 'inherit' });
    console.log('\x1b[32m✔ Backend dependencies installed.\x1b[0m\n');
  } catch (e) {
    console.error('\x1b[31m✖ Failed to install backend dependencies:\x1b[0m', e.message);
  }
}

// 3. Install Frontend Dependencies
console.log('\x1b[33m📦 Installing Frontend dependencies (npm install)...\x1b[0m');
try {
  execSync(`${npmCmd} install`, { cwd: frontendDir, stdio: 'inherit' });
  console.log('\x1b[32m✔ Frontend dependencies installed.\x1b[0m\n');
} catch (e) {
  console.error('\x1b[31m✖ Failed to install frontend dependencies:\x1b[0m', e.message);
}

// 4. Install Root devDependencies (if any)
console.log('\x1b[33m📦 Installing Root dependencies...\x1b[0m');
try {
  execSync(`${npmCmd} install`, { cwd: rootDir, stdio: 'inherit' });
  console.log('\x1b[32m✔ Root dependencies installed.\x1b[0m\n');
} catch (e) {
  console.log('\x1b[90m(Root dependencies skipped or already up to date)\x1b[0m\n');
}

console.log('\x1b[1m\x1b[32m🎉 Setup Completed Successfully!\x1b[0m');
console.log('\x1b[36mYou can now run:\x1b[0m');
console.log('  \x1b[1mnpm run dev\x1b[0m    - Run both Backend & Frontend in dev mode');
console.log('  \x1b[1mnpm start\x1b[0m      - Build and run unified server on port 8000');
console.log('  \x1b[1mnpm test\x1b[0m       - Run backend tests\n');
