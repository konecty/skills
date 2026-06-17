#!/usr/bin/env node
// duplication.js — detects copy-paste code duplication via jscpd
// Usage: node duplication.js --repo <abs-path> --out <abs-path-to-json>

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// --- arg parsing ---
const argv = process.argv.slice(2);
let repoPath = null;
let outPath = null;

for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--repo') repoPath = argv[++i];
  else if (argv[i] === '--out') outPath = argv[++i];
}

if (!repoPath || !outPath) {
  const msg = { layer: 'duplication', lang: 'typescript', error: true, error_message: '--repo and --out are required' };
  process.stdout.write(JSON.stringify(msg, null, 2) + '\n');
  process.exit(0);
}

fs.mkdirSync(path.dirname(outPath), { recursive: true });

// Temp dir for jscpd output
const tmpDir = path.join(os.tmpdir(), 'codebase-intelligence-jscpd');
fs.mkdirSync(tmpDir, { recursive: true });

const reportPath = path.join(tmpDir, 'jscpd-report.json');

// --- run jscpd ---
let jscpdRaw = null;
try {
  execSync(
    [
      'npx --yes jscpd .',
      '--reporters json',
      `--output "${tmpDir}"`,
      '--ignore "node_modules,dist,.next,build,coverage,.codebase-audit,.python-audit"',
      '--languages javascript,typescript',
      '--min-lines 5',
      '--min-tokens 50',
      '--format json',
    ].join(' '),
    { cwd: repoPath, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
  );
} catch (err) {
  const errMsg = (err.stderr || err.message || '').toLowerCase();
  if (errMsg.includes('not found') || errMsg.includes('command not found') || errMsg.includes('cannot find')) {
    const out = { layer: 'duplication', lang: 'typescript', error: true, error_message: 'jscpd not found — install with: npm install -g jscpd' };
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
    process.exit(0);
  }
  // jscpd may exit non-zero but still produce report — continue
}

// Read the report file
try {
  const raw = fs.readFileSync(reportPath, 'utf8');
  jscpdRaw = JSON.parse(raw);
} catch (err) {
  const out = { layer: 'duplication', lang: 'typescript', error: true, error_message: `Failed to read/parse jscpd report: ${err.message}` };
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  process.exit(0);
}

// --- normalize output ---
const duplicates = Array.isArray(jscpdRaw.duplicates) ? jscpdRaw.duplicates : [];
const stats = (jscpdRaw.statistics && jscpdRaw.statistics.total) || {};

const findings = [];
let totalDuplicatedLines = 0;

duplicates.forEach((dup, idx) => {
  const lines = dup.lines || 0;
  totalDuplicatedLines += lines;
  findings.push({
    clone_id: `g${idx + 1}`,
    lines,
    instances: [
      { path: dup.firstFile.name, start: dup.firstFile.start, end: dup.firstFile.end },
      { path: dup.secondFile.name, start: dup.secondFile.start, end: dup.secondFile.end },
    ],
    action: { type: 'extract_shared_helper', auto_fixable: false },
  });
});

const output = {
  layer: 'duplication',
  lang: 'typescript',
  findings,
  counts: {
    clone_groups: findings.length,
    duplicated_lines: totalDuplicatedLines,
  },
  summary: {
    duplication_rate_pct: typeof stats.percentage === 'number' ? stats.percentage : null,
    total_lines: typeof stats.lines === 'number' ? stats.lines : null,
  },
};

fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
process.exit(0);
