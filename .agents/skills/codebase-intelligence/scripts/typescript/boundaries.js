#!/usr/bin/env node
// boundaries.js — detects circular imports and architecture boundary violations
// via dependency-cruiser.
// Usage: node boundaries.js --repo <abs-path> --out <abs-path-to-json>

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
  const msg = { layer: 'boundaries', lang: 'typescript', error: true, error_message: '--repo and --out are required' };
  process.stdout.write(JSON.stringify(msg, null, 2) + '\n');
  process.exit(0);
}

fs.mkdirSync(path.dirname(outPath), { recursive: true });

// --- detect config file ---
const configCjs = path.join(repoPath, '.dependency-cruiser.cjs');
const configJs = path.join(repoPath, '.dependency-cruiser.js');
const hasConfig = fs.existsSync(configCjs) || fs.existsSync(configJs);

// --- build command ---
let depcruiseCmd;
if (hasConfig) {
  depcruiseCmd = 'npx --yes depcruise --validate --output-type json src';
} else {
  depcruiseCmd = [
    'npx --yes depcruise',
    '--output-type json',
    '--exclude "node_modules|dist|build|coverage"',
    '--include-only "^src"',
    'src',
  ].join(' ');
}

// --- run dependency-cruiser ---
let dcOutput = '';
try {
  dcOutput = execSync(depcruiseCmd, {
    cwd: repoPath,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
} catch (err) {
  // depcruise exits non-zero when it finds violations — parse stdout anyway
  dcOutput = err.stdout || '';
  if (!dcOutput.trim()) {
    const errMsg = (err.stderr || err.message || '').toLowerCase();
    if (
      errMsg.includes('not found') ||
      errMsg.includes('command not found') ||
      errMsg.includes('cannot find') ||
      errMsg.includes('is not recognized')
    ) {
      const out = { layer: 'boundaries', lang: 'typescript', error: true, error_message: 'dependency-cruiser not found — install with: npm install -g dependency-cruiser' };
      fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
      process.exit(0);
    }
    // src dir may not exist
    const out = { layer: 'boundaries', lang: 'typescript', error: true, error_message: `dependency-cruiser failed: ${err.message}` };
    fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
    process.exit(0);
  }
}

// --- parse output ---
let dcData = null;
try {
  dcData = JSON.parse(dcOutput);
} catch (parseErr) {
  const out = { layer: 'boundaries', lang: 'typescript', error: true, error_message: `Failed to parse dependency-cruiser output: ${parseErr.message}` };
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2));
  process.exit(0);
}

// --- extract circular imports from modules ---
const findings = [];
const seenCycles = new Set();

const modules = Array.isArray(dcData.modules) ? dcData.modules : [];
for (const mod of modules) {
  const deps = Array.isArray(mod.dependencies) ? mod.dependencies : [];
  for (const dep of deps) {
    if (!dep.circular) continue;
    // Build a minimal cycle representation: [source, resolved, source]
    const cycleKey = [mod.source, dep.resolved].sort().join('|');
    if (seenCycles.has(cycleKey)) continue;
    seenCycles.add(cycleKey);
    findings.push({
      kind: 'circular_import',
      cycle: [mod.source, dep.resolved, mod.source],
    });
  }
}

// --- extract boundary violations from summary ---
const summary = dcData.summary || {};
const violations = Array.isArray(summary.violations) ? summary.violations : [];
for (const v of violations) {
  // Skip if it's just a circular dependency already captured above
  const rule = (v.rule && v.rule.name) || '';
  findings.push({
    kind: 'boundary_violation',
    from: v.from,
    to: v.to,
    rule,
    severity: (v.rule && v.rule.severity) || 'error',
  });
}

const circularCount = findings.filter(f => f.kind === 'circular_import').length;
const boundaryCount = findings.filter(f => f.kind === 'boundary_violation').length;

const output = {
  layer: 'boundaries',
  lang: 'typescript',
  has_config: hasConfig,
  findings,
  counts: {
    boundary_violations: boundaryCount,
    circular_imports: circularCount,
  },
};

fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
process.exit(0);
