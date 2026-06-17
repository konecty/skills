#!/usr/bin/env node
// hotspots.js — detects high-risk files: churn (git) × complexity
// Usage: node hotspots.js --repo <abs-path> --out <abs-path-to-json>

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const REFACTOR_THRESHOLD = 50;

// --- arg parsing ---
const argv = process.argv.slice(2);
let repoPath = null;
let outPath = null;

for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--repo') repoPath = argv[++i];
  else if (argv[i] === '--out') outPath = argv[++i];
}

if (!repoPath || !outPath) {
  const msg = { layer: 'hotspots', lang: 'typescript', error: true, error_message: '--repo and --out are required' };
  process.stdout.write(JSON.stringify(msg, null, 2) + '\n');
  process.exit(0);
}

fs.mkdirSync(path.dirname(outPath), { recursive: true });

const outDir = path.dirname(outPath);
const rawDir = path.join(outDir, 'raw', 'typescript');

// --- Step 1: git log churn ---
let gitLogOutput = '';
try {
  gitLogOutput = execSync(
    'git log --since="90 days ago" --name-only --pretty=format: HEAD',
    { cwd: repoPath, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
  );
} catch (err) {
  const errMsg = (err.stderr || err.message || '').toLowerCase();
  if (errMsg.includes('not a git repository') || errMsg.includes('not found')) {
    const out = { layer: 'hotspots', lang: 'typescript', error: true, error_message: `git log failed: ${err.message}` };
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
    process.exit(0);
  }
  // Use partial output if available
  gitLogOutput = err.stdout || '';
}

// Filter and count TS/JS files
const tsJsPattern = /\.(ts|tsx|js|jsx)$/;
const churnMap = {};
let totalLines = 0;

for (const rawLine of gitLogOutput.split('\n')) {
  const line = rawLine.trim();
  if (!line) continue;
  totalLines++;
  if (tsJsPattern.test(line)) {
    churnMap[line] = (churnMap[line] || 0) + 1;
  }
}

// Emit a warning if fewer than 30 total file entries (sparse history)
const warnings = [];
if (totalLines < 30) {
  warnings.push(`Sparse git history: only ${totalLines} file-change entries in last 90 days. Hotspot scores may not be reliable.`);
}

// --- Step 2: read complexity index ---
const rawComplexityPath = path.join(rawDir, 'complexity.json');
let complexityByFile = {};
try {
  if (fs.existsSync(rawComplexityPath)) {
    complexityByFile = JSON.parse(fs.readFileSync(rawComplexityPath, 'utf8'));
  }
} catch (e) {
  // non-fatal — use default max_cyclomatic = 1
}

// --- Step 3: compute scores ---
const hotspots = [];

for (const [filePath, churnCount] of Object.entries(churnMap)) {
  const maxCyclomatic = complexityByFile[filePath] || 1;
  const score = churnCount * maxCyclomatic;
  hotspots.push({
    path: filePath,
    commits_last_90d: churnCount,
    max_cyclomatic: maxCyclomatic,
    score,
    verdict: score >= REFACTOR_THRESHOLD ? 'refactor_target' : 'watch',
  });
}

// Sort by score descending
hotspots.sort((a, b) => b.score - a.score);

const refactorTargets = hotspots.filter(h => h.verdict === 'refactor_target');
const topFile = hotspots.length > 0 ? hotspots[0] : null;

const output = {
  layer: 'hotspots',
  lang: 'typescript',
  findings: hotspots,
  counts: {
    refactor_targets: refactorTargets.length,
  },
  summary: {
    top_file: topFile ? topFile.path : null,
    top_score: topFile ? topFile.score : null,
    warnings,
  },
};

fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
process.exit(0);
