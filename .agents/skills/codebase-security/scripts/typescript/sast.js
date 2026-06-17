#!/usr/bin/env node
/**
 * Layer 4 (TypeScript/JavaScript) — SAST: insecure code patterns.
 *
 * Primary tool: semgrep with the registry security ruleset (if on PATH —
 * semgrep covers JS/TS natively and is the best engine here).
 * Fallback: builtin regex ruleset covering the classic JS sinks. Lower
 * coverage, flagged as such, but the layer never silently goes green.
 */
'use strict';

const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const EXCLUDE_DIRS = new Set([
  '.git', 'node_modules', 'dist', 'build', '.next', '.turbo', 'coverage',
  '.venv', 'venv', '.security-audit', '.codebase-audit', '__generated__',
]);
const TEST_RE = /(^|\/)(tests?|__tests__|__mocks__|e2e|fixtures)(\/|$)|\.(test|spec)\.[jt]sx?$/;
const CODE_RE = /\.(ts|tsx|js|jsx|mjs|cjs)$/;

// rule, severity, cwe, message, pattern
const BUILTIN_RULES = [
  ['js-eval', 'high', 'CWE-95', 'eval() executes arbitrary strings as code',
    /\beval\s*\(/],
  ['js-new-function', 'high', 'CWE-95', 'new Function() is eval in disguise',
    /\bnew\s+Function\s*\(/],
  ['js-child-process-concat', 'high', 'CWE-78', 'Shell command built from template/concatenation — command injection risk',
    /\b(exec|execSync)\s*\(\s*(`[^`]*\$\{|['"][^'"]*['"]\s*\+)/],
  ['js-dangerously-set-html', 'medium', 'CWE-79', 'dangerouslySetInnerHTML — XSS if content is not sanitised',
    /dangerouslySetInnerHTML/],
  ['js-innerhtml-assign', 'medium', 'CWE-79', 'Direct innerHTML assignment — XSS if content is not sanitised',
    /\.innerHTML\s*=/],
  ['js-document-write', 'medium', 'CWE-79', 'document.write with dynamic content — XSS vector',
    /document\.write(ln)?\s*\(/],
  ['js-deprecated-cipher', 'high', 'CWE-327', 'crypto.createCipher is broken (no IV) — use createCipheriv',
    /crypto\.createCipher\s*\(/],
  ['js-weak-random-secret', 'medium', 'CWE-338', 'Math.random() used near token/secret generation — not cryptographically secure',
    /(token|secret|nonce|otp|password)[^\n]{0,40}Math\.random|Math\.random[^\n]{0,40}(token|secret|nonce|otp|password)/i],
  ['js-tls-reject-unauthorized', 'high', 'CWE-295', 'TLS certificate validation disabled',
    /rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED/],
  ['js-prototype-pollution-merge', 'low', 'CWE-1321', 'Recursive merge of untrusted objects can enable prototype pollution',
    /\b(deepMerge|mergeDeep|defaultsDeep)\s*\(/],
  ['js-sql-template', 'high', 'CWE-89', 'SQL built from template interpolation — use parameterised queries',
    /\.(query|execute)\s*\(\s*`[^`]*\$\{/],
  ['js-http-url-fetch', 'low', 'CWE-319', 'Plain http:// request — credentials/data travel unencrypted',
    /(fetch|axios[.(]\w*)\s*\(\s*['"`]http:\/\/(?!localhost|127\.0\.0\.1|0\.0\.0\.0)/],
];

function walk(dir, repo, acc) {
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return acc; }
  for (const e of entries) {
    if (EXCLUDE_DIRS.has(e.name)) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walk(full, repo, acc);
    else if (CODE_RE.test(e.name)) acc.push(full);
  }
  return acc;
}

function runSemgrep(repo) {
  const probe = spawnSync('semgrep', ['--version'], { encoding: 'utf8' });
  if (probe.error || probe.status !== 0) return null;
  const res = spawnSync('semgrep', [
    'scan', '--config', 'p/security-audit', '--json', '--quiet',
    '--metrics', 'off', '--timeout', '120', repo,
  ], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, timeout: 900_000 });
  if (!res.stdout) return null;
  let data;
  try { data = JSON.parse(res.stdout); } catch { return null; }
  const sevMap = { ERROR: 'high', WARNING: 'medium', INFO: 'low' };
  const findings = [];
  for (const it of data.results || []) {
    let p = it.path || '?';
    if (p.startsWith(repo)) p = path.relative(repo, p);
    if (!CODE_RE.test(p)) continue;
    const extra = it.extra || {};
    findings.push({
      path: p,
      line: (it.start || {}).line || 0,
      rule: it.check_id || '?',
      rule_name: (it.check_id || '?').split('.').pop(),
      severity: sevMap[extra.severity] || 'low',
      confidence: 'medium',
      message: (extra.message || '').slice(0, 300),
      cwe: Array.isArray((extra.metadata || {}).cwe) ? String(extra.metadata.cwe[0]).slice(0, 8) : '',
      in_test_file: TEST_RE.test(p),
      tool: 'semgrep',
    });
  }
  return findings;
}

function runBuiltin(repo, targets) {
  const files = targets.length ? targets : walk(repo, repo, []);
  const findings = [];
  for (const file of files) {
    if (!CODE_RE.test(file)) continue;
    let text;
    try {
      if (fs.statSync(file).size > 500_000) continue;
      text = fs.readFileSync(file, 'utf8');
    } catch { continue; }
    const rel = path.isAbsolute(file) ? path.relative(repo, file) : file;
    const lines = text.split('\n');
    for (let i = 0; i < lines.length; i++) {
      for (const [rule, severity, cwe, message, pattern] of BUILTIN_RULES) {
        if (pattern.test(lines[i])) {
          findings.push({
            path: rel,
            line: i + 1,
            rule,
            rule_name: rule,
            severity,
            confidence: 'medium',
            message,
            cwe,
            in_test_file: TEST_RE.test(rel),
            tool: 'builtin-regex',
          });
          break;
        }
      }
    }
  }
  return findings;
}

function main() {
  const args = process.argv.slice(2);
  const repo = path.resolve(args[0]);
  const outIdx = args.indexOf('--out');
  const targetsIdx = args.indexOf('--targets');
  const out = args[outIdx + 1];

  // Targets file absent = full scan; present = diff scope (no JS/TS → skip).
  const diffScope = targetsIdx !== -1 && fs.existsSync(args[targetsIdx + 1]);
  let targets = [];
  if (diffScope) {
    targets = fs.readFileSync(args[targetsIdx + 1], 'utf8')
      .split('\n').map((l) => l.trim())
      .filter((l) => l && CODE_RE.test(l) && fs.existsSync(path.join(repo, l)))
      .map((l) => path.join(repo, l));
    if (!targets.length) {
      fs.mkdirSync(path.dirname(out), { recursive: true });
      fs.writeFileSync(out, JSON.stringify({
        layer: 'sast', skipped: true, reason: 'no changed JS/TS files in scope',
        findings: [], counts: { total: 0, high_actionable: 0 },
      }, null, 2));
      console.log('sast(ts): skipped (no changed JS/TS files)');
      return;
    }
  }

  let tool = 'semgrep';
  let findings = targets.length ? null : runSemgrep(repo);
  const warnings = [];
  if (findings === null) {
    tool = 'builtin-regex';
    findings = runBuiltin(repo, targets);
    if (!targets.length) {
      warnings.push('semgrep not available — used builtin regex ruleset (lower coverage). Install: brew install semgrep');
    }
  }

  const high = findings.filter((f) => f.severity === 'high' && !f.in_test_file).length;
  const payload = {
    layer: 'sast',
    tool,
    fallback_used: tool === 'builtin-regex',
    findings,
    counts: {
      total: findings.length,
      high_actionable: high,
      by_severity: {
        high: findings.filter((f) => f.severity === 'high').length,
        medium: findings.filter((f) => f.severity === 'medium').length,
        low: findings.filter((f) => f.severity === 'low').length,
      },
    },
    warnings,
  };
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(payload, null, 2));
  console.log(`sast(ts): ${findings.length} findings (${high} high outside tests) via ${tool}`);
}

main();
