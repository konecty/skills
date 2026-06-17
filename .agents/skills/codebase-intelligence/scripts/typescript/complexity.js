#!/usr/bin/env node
// complexity.js — detects functions with high cyclomatic complexity via ESLint
// Usage: node complexity.js --repo <abs-path> --out <abs-path-to-json>

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const CC_WARN = 10;
const CC_FAIL = 25;

// --- arg parsing ---
const argv = process.argv.slice(2);
let repoPath = null;
let outPath = null;

for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--repo') repoPath = argv[++i];
  else if (argv[i] === '--out') outPath = argv[++i];
}

if (!repoPath || !outPath) {
  const msg = { layer: 'complexity', lang: 'typescript', error: true, error_message: '--repo and --out are required' };
  process.stdout.write(JSON.stringify(msg, null, 2) + '\n');
  process.exit(0);
}

fs.mkdirSync(path.dirname(outPath), { recursive: true });

// Also save raw complexity data for hotspots.js
const outDir = path.dirname(outPath);
const rawDir = path.join(outDir, 'raw', 'typescript');
fs.mkdirSync(rawDir, { recursive: true });
const rawComplexityPath = path.join(rawDir, 'complexity.json');

// --- run eslint ---
const eslintCmd = [
  'npx --yes eslint',
  '--no-eslintrc',
  '--parser-options "ecmaVersion:2022,sourceType:module"',
  '--rule "complexity: [error, 10]"',
  '--format json',
  '--ext .ts,.tsx,.js,.jsx',
  '.',
].join(' ');

let eslintOutput = '';
try {
  eslintOutput = execSync(eslintCmd, {
    cwd: repoPath,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
} catch (err) {
  // ESLint exits non-zero when it finds violations — that's expected
  eslintOutput = err.stdout || '';
  if (!eslintOutput.trim()) {
    const errMsg = (err.stderr || err.message || '').toLowerCase();
    if (errMsg.includes('not found') || errMsg.includes('command not found') || errMsg.includes('cannot find')) {
      const out = { layer: 'complexity', lang: 'typescript', error: true, error_message: 'eslint not found — install with: npm install -g eslint' };
      fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
      process.exit(0);
    }
    const out = { layer: 'complexity', lang: 'typescript', error: true, error_message: `eslint failed with no output: ${err.message}` };
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
    process.exit(0);
  }
}

// --- parse eslint output ---
let eslintData = [];
try {
  eslintData = JSON.parse(eslintOutput);
} catch (parseErr) {
  const out = { layer: 'complexity', lang: 'typescript', error: true, error_message: `Failed to parse ESLint JSON output: ${parseErr.message}` };
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  process.exit(0);
}

// regex to extract function name and complexity value from message
const msgRegex = /Function '(.+)' has a complexity of (\d+)/;

const findings = [];
const complexityByFile = {};

for (const fileResult of eslintData) {
  const relPath = path.relative(repoPath, fileResult.filePath);
  for (const msg of (fileResult.messages || [])) {
    if (msg.ruleId !== 'complexity') continue;
    const match = msgRegex.exec(msg.message);
    if (!match) continue;
    const funcName = match[1];
    const cyclomatic = parseInt(match[2], 10);
    const verdict = cyclomatic >= CC_FAIL ? 'above_threshold' : 'warn';

    findings.push({
      path: relPath,
      function: funcName,
      line: msg.line,
      cyclomatic,
      verdict,
    });

    // track max cyclomatic per file for hotspots
    if (!complexityByFile[relPath] || complexityByFile[relPath] < cyclomatic) {
      complexityByFile[relPath] = cyclomatic;
    }
  }
}

const aboveThreshold = findings.filter(f => f.verdict === 'above_threshold').length;
const warnCount = findings.filter(f => f.verdict === 'warn').length;
const avgComplexity = findings.length > 0
  ? Math.round((findings.reduce((sum, f) => sum + f.cyclomatic, 0) / findings.length) * 10) / 10
  : 0;

const output = {
  layer: 'complexity',
  lang: 'typescript',
  findings,
  counts: {
    above_threshold: aboveThreshold,
    warn: warnCount,
    total: findings.length,
  },
  summary: {
    avg_complexity: avgComplexity,
  },
};

// Save raw complexity index for hotspots.js
try {
  fs.writeFileSync(rawComplexityPath, JSON.stringify(complexityByFile, null, 2));
} catch (e) {
  // non-fatal
}

fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
process.exit(0);
