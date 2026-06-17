#!/usr/bin/env node
// dead_code.js — detects unused exports, files, types via knip
// Usage: node dead_code.js --repo <abs-path> --out <abs-path-to-json>

'use strict';

const fs = require('fs');
const path = require('path');
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
  const msg = { layer: 'dead_code', lang: 'typescript', error: true, error_message: '--repo and --out are required' };
  process.stdout.write(JSON.stringify(msg, null, 2) + '\n');
  process.exit(0);
}

// Derive raw output directory: <out_dir>/raw/typescript/
const outDir = path.dirname(outPath);
const rawDir = path.join(outDir, 'raw', 'typescript');
fs.mkdirSync(rawDir, { recursive: true });
fs.mkdirSync(path.dirname(outPath), { recursive: true });

const rawKnipPath = path.join(rawDir, 'knip_raw.json');

// --- run knip ---
let knipRaw = null;
try {
  const stdout = execSync(
    'npx --yes knip --reporter json --no-progress 2>/dev/null',
    { cwd: repoPath, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
  );
  knipRaw = JSON.parse(stdout);
} catch (err) {
  // knip may exit non-zero when it finds issues; try to parse stdout anyway
  const stdout = err.stdout || '';
  if (!stdout.trim()) {
    // tool truly not found or no output
    const errMsg = (err.stderr || err.message || '').toLowerCase();
    if (errMsg.includes('not found') || errMsg.includes('command not found') || errMsg.includes('cannot find')) {
      const out = { layer: 'dead_code', lang: 'typescript', error: true, error_message: 'knip not found — install with: npm install -g knip' };
      fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
      process.exit(0);
    }
    const out = { layer: 'dead_code', lang: 'typescript', error: true, error_message: `knip failed: ${err.message}` };
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
    process.exit(0);
  }
  try {
    knipRaw = JSON.parse(stdout);
  } catch (parseErr) {
    const out = { layer: 'dead_code', lang: 'typescript', error: true, error_message: `Failed to parse knip output: ${parseErr.message}` };
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
    process.exit(0);
  }
}

// Save raw knip output for dependencies.js to reuse
try {
  fs.writeFileSync(rawKnipPath, JSON.stringify(knipRaw, null, 2));
} catch (e) {
  // non-fatal
}

// --- normalize output ---
const findings = [];

// unused files
const unusedFiles = Array.isArray(knipRaw.files) ? knipRaw.files : [];
for (const filePath of unusedFiles) {
  findings.push({
    path: filePath,
    kind: 'unused_file',
    name: filePath,
    tool: 'knip',
    action: { type: 'delete', auto_fixable: false },
  });
}

// unused exports
const unusedExports = Array.isArray(knipRaw.exports) ? knipRaw.exports : [];
for (const exp of unusedExports) {
  findings.push({
    path: exp.file,
    line: exp.line,
    kind: 'unused_export',
    name: exp.symbol,
    tool: 'knip',
    action: { type: 'delete', auto_fixable: true },
  });
}

// unused types
const unusedTypes = Array.isArray(knipRaw.types) ? knipRaw.types : [];
for (const t of unusedTypes) {
  findings.push({
    path: t.file,
    line: t.line,
    kind: 'unused_type',
    name: t.symbol,
    tool: 'knip',
    action: { type: 'delete', auto_fixable: true },
  });
}

// unused enum members
const enumMembers = knipRaw.enumMembers || {};
for (const [file, members] of Object.entries(enumMembers)) {
  if (!Array.isArray(members)) continue;
  for (const member of members) {
    findings.push({
      path: member.file || file,
      line: member.line,
      kind: 'unused_enum_member',
      name: member.symbol,
      tool: 'knip',
      action: { type: 'delete', auto_fixable: true },
    });
  }
}

// unused class members
const classMembers = knipRaw.classMembers || {};
for (const [file, members] of Object.entries(classMembers)) {
  if (!Array.isArray(members)) continue;
  for (const member of members) {
    findings.push({
      path: member.file || file,
      line: member.line,
      kind: 'unused_class_member',
      name: member.symbol,
      tool: 'knip',
      action: { type: 'delete', auto_fixable: false },
    });
  }
}

const counts = {
  unused_files: unusedFiles.length,
  unused_exports: unusedExports.length,
  unused_types: unusedTypes.length,
  total: findings.length,
};

const output = {
  layer: 'dead_code',
  lang: 'typescript',
  findings,
  counts,
};

fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
process.exit(0);
