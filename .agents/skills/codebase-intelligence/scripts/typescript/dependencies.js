#!/usr/bin/env node
// dependencies.js — detects unused/unlisted npm dependencies via knip
// Reuses knip_raw.json written by dead_code.js if available; re-runs knip otherwise.
// Usage: node dependencies.js --repo <abs-path> --out <abs-path-to-json>

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
  const msg = { layer: 'dependencies', lang: 'typescript', error: true, error_message: '--repo and --out are required' };
  process.stdout.write(JSON.stringify(msg, null, 2) + '\n');
  process.exit(0);
}

fs.mkdirSync(path.dirname(outPath), { recursive: true });

const outDir = path.dirname(outPath);
const rawDir = path.join(outDir, 'raw', 'typescript');
const rawKnipPath = path.join(rawDir, 'knip_raw.json');

// --- load or re-run knip ---
let knipRaw = null;

// Try to reuse cached knip output
if (fs.existsSync(rawKnipPath)) {
  try {
    knipRaw = JSON.parse(fs.readFileSync(rawKnipPath, 'utf8'));
  } catch (e) {
    knipRaw = null;
  }
}

if (!knipRaw) {
  // Re-run knip
  try {
    const stdout = execSync(
      'npx --yes knip --reporter json --no-progress 2>/dev/null',
      { cwd: repoPath, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }
    );
    knipRaw = JSON.parse(stdout);
  } catch (err) {
    const stdout = err.stdout || '';
    if (!stdout.trim()) {
      const errMsg = (err.stderr || err.message || '').toLowerCase();
      if (errMsg.includes('not found') || errMsg.includes('command not found') || errMsg.includes('cannot find')) {
        const out = { layer: 'dependencies', lang: 'typescript', error: true, error_message: 'knip not found — install with: npm install -g knip' };
        fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
        process.exit(0);
      }
      const out = { layer: 'dependencies', lang: 'typescript', error: true, error_message: `knip failed: ${err.message}` };
      fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
      process.exit(0);
    }
    try {
      knipRaw = JSON.parse(stdout);
    } catch (parseErr) {
      const out = { layer: 'dependencies', lang: 'typescript', error: true, error_message: `Failed to parse knip output: ${parseErr.message}` };
      fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
      process.exit(0);
    }
  }

  // Cache the raw output
  try {
    fs.mkdirSync(rawDir, { recursive: true });
    fs.writeFileSync(rawKnipPath, JSON.stringify(knipRaw, null, 2));
  } catch (e) {
    // non-fatal
  }
}

// --- normalize output ---
const findings = [];

const unusedDeps = Array.isArray(knipRaw.dependencies) ? knipRaw.dependencies : [];
for (const dep of unusedDeps) {
  const name = typeof dep === 'string' ? dep : dep.name || String(dep);
  findings.push({ name, kind: 'unused_dependency', tool: 'knip' });
}

const unusedDevDeps = Array.isArray(knipRaw.devDependencies) ? knipRaw.devDependencies : [];
for (const dep of unusedDevDeps) {
  const name = typeof dep === 'string' ? dep : dep.name || String(dep);
  findings.push({ name, kind: 'unused_devDependency', tool: 'knip' });
}

const unlisted = Array.isArray(knipRaw.unlisted) ? knipRaw.unlisted : [];
for (const dep of unlisted) {
  const name = typeof dep === 'string' ? dep : dep.name || String(dep);
  findings.push({ name, kind: 'unlisted', tool: 'knip' });
}

const unusedCount = unusedDeps.length + unusedDevDeps.length;
const unlistedCount = unlisted.length;

const output = {
  layer: 'dependencies',
  lang: 'typescript',
  findings,
  counts: {
    unused: unusedCount,
    unlisted: unlistedCount,
    total: findings.length,
  },
};

fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
process.exit(0);
