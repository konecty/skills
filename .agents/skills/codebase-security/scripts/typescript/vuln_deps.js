#!/usr/bin/env node
/**
 * Layer 5 (TypeScript/JavaScript) — known-vulnerable dependencies (SCA).
 *
 * Picks the audit command from the lockfile present:
 *   package-lock.json → npm audit --json
 *   pnpm-lock.yaml    → pnpm audit --json
 *   yarn.lock         → yarn audit --json (classic, ndjson)
 *
 * osv-scanner (if on PATH) runs additionally and is merged in — it is the
 * only one of these that flags OSV `MAL-` malicious-package advisories.
 * All of them need network access; offline → skipped with warning.
 */
'use strict';

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const SEV_ORDER = { critical: 4, high: 3, moderate: 2, medium: 2, low: 1, info: 0 };

function normSev(s) {
  s = String(s || 'unknown').toLowerCase();
  return s === 'moderate' ? 'medium' : (SEV_ORDER[s] !== undefined ? s : 'unknown');
}

function run(cmd, args, cwd) {
  return spawnSync(cmd, args, {
    cwd, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, timeout: 600_000,
  });
}

function npmAudit(repo) {
  const res = run('npm', ['audit', '--json'], repo);
  if (!res.stdout || !res.stdout.trim().startsWith('{')) return null;
  let data;
  try { data = JSON.parse(res.stdout); } catch { return null; }
  const vulns = data.vulnerabilities || {};
  const findings = [];
  for (const [name, v] of Object.entries(vulns)) {
    const advisories = (v.via || []).filter((x) => typeof x === 'object');
    findings.push({
      package: name,
      version: v.range || '?',
      vuln_id: advisories[0] ? (advisories[0].url || advisories[0].title || '?') : 'transitive',
      aliases: advisories.map((a) => a.cve || a.title).filter(Boolean).slice(0, 5),
      severity: normSev(v.severity),
      malicious: false,
      summary: advisories[0] ? String(advisories[0].title || '').slice(0, 200) : `via ${(v.via || []).filter((x) => typeof x === 'string').join(', ')}`,
      fixed_in: v.fixAvailable ? [typeof v.fixAvailable === 'object' ? `${v.fixAvailable.name}@${v.fixAvailable.version}` : 'run npm audit fix'] : [],
      direct: !!v.isDirect,
      manifest: 'package-lock.json',
      tool: 'npm-audit',
    });
  }
  return findings;
}

function pnpmAudit(repo) {
  const res = run('pnpm', ['audit', '--json'], repo);
  if (!res.stdout || !res.stdout.trim().startsWith('{')) return null;
  let data;
  try { data = JSON.parse(res.stdout); } catch { return null; }
  const findings = [];
  for (const adv of Object.values(data.advisories || {})) {
    findings.push({
      package: adv.module_name,
      version: adv.vulnerable_versions || '?',
      vuln_id: (adv.cves || [])[0] || `GHSA:${adv.github_advisory_id || adv.id}`,
      aliases: adv.cves || [],
      severity: normSev(adv.severity),
      malicious: false,
      summary: String(adv.title || '').slice(0, 200),
      fixed_in: adv.patched_versions ? [adv.patched_versions] : [],
      direct: false,
      manifest: 'pnpm-lock.yaml',
      tool: 'pnpm-audit',
    });
  }
  return findings;
}

function yarnAudit(repo) {
  const res = run('yarn', ['audit', '--json'], repo);
  if (!res.stdout) return null;
  const findings = [];
  for (const line of res.stdout.split('\n')) {
    if (!line.trim().startsWith('{')) continue;
    let row;
    try { row = JSON.parse(line); } catch { continue; }
    if (row.type !== 'auditAdvisory') continue;
    const adv = row.data.advisory;
    findings.push({
      package: adv.module_name,
      version: adv.vulnerable_versions || '?',
      vuln_id: (adv.cves || [])[0] || `advisory:${adv.id}`,
      aliases: adv.cves || [],
      severity: normSev(adv.severity),
      malicious: false,
      summary: String(adv.title || '').slice(0, 200),
      fixed_in: adv.patched_versions ? [adv.patched_versions] : [],
      direct: false,
      manifest: 'yarn.lock',
      tool: 'yarn-audit',
    });
  }
  return findings;
}

function osvScanner(repo) {
  const probe = spawnSync('osv-scanner', ['--version'], { encoding: 'utf8' });
  if (probe.error) return null;
  for (const args of [
    ['scan', 'source', '-r', '--format', 'json', repo],
    ['--recursive', '--format', 'json', repo],
  ]) {
    const res = run('osv-scanner', args, repo);
    if (!res.stdout || !res.stdout.trim().startsWith('{')) continue;
    let data;
    try { data = JSON.parse(res.stdout); } catch { continue; }
    const findings = [];
    for (const r of data.results || []) {
      for (const pkg of r.packages || []) {
        const info = pkg.package || {};
        if (info.ecosystem !== 'npm') continue;
        for (const vuln of pkg.vulnerabilities || []) {
          const malicious = String(vuln.id || '').startsWith('MAL-') ||
            (vuln.aliases || []).some((a) => String(a).startsWith('MAL-'));
          const dbSev = ((vuln.database_specific || {}).severity || '').toLowerCase();
          findings.push({
            package: info.name,
            version: info.version,
            vuln_id: vuln.id,
            aliases: vuln.aliases || [],
            severity: malicious ? 'critical' : normSev(dbSev),
            malicious,
            summary: String(vuln.summary || '').slice(0, 200),
            fixed_in: [],
            direct: false,
            manifest: (r.source || {}).path || '?',
            tool: 'osv-scanner',
          });
        }
      }
    }
    return findings;
  }
  return null;
}

function main() {
  const args = process.argv.slice(2);
  const repo = path.resolve(args[0]);
  const out = args[args.indexOf('--out') + 1];
  fs.mkdirSync(path.dirname(out), { recursive: true });

  const warnings = [];
  let findings = null;
  let tool = 'none';

  if (fs.existsSync(path.join(repo, 'package-lock.json'))) {
    findings = npmAudit(repo); tool = 'npm-audit';
  } else if (fs.existsSync(path.join(repo, 'pnpm-lock.yaml'))) {
    findings = pnpmAudit(repo); tool = 'pnpm-audit';
  } else if (fs.existsSync(path.join(repo, 'yarn.lock'))) {
    findings = yarnAudit(repo); tool = 'yarn-audit';
  } else {
    warnings.push('no lockfile found — package-manager audit cannot run (also flagged by supply_chain layer)');
  }
  if (findings === null && tool !== 'none') {
    warnings.push(`${tool} failed (offline? registry unreachable?)`);
    findings = null;
  }

  // Merge osv-scanner results (dedupe on package+vuln_id).
  const osv = osvScanner(repo);
  if (osv) {
    const seen = new Set((findings || []).map((f) => `${f.package}|${f.vuln_id}`));
    findings = (findings || []).concat(osv.filter((f) => !seen.has(`${f.package}|${f.vuln_id}`)));
    tool = tool === 'none' ? 'osv-scanner' : `${tool}+osv-scanner`;
  }

  let payload;
  if (findings === null) {
    payload = {
      layer: 'vuln_deps', skipped: true,
      reason: warnings.join('; ') || 'no SCA tool succeeded',
      findings: [], counts: { total: 0 }, warnings,
    };
    console.log(`vuln_deps(ts): SKIPPED — ${payload.reason}`);
  } else {
    const bySev = {};
    for (const s of ['critical', 'high', 'medium', 'low', 'unknown']) {
      bySev[s] = findings.filter((f) => f.severity === s).length;
    }
    payload = {
      layer: 'vuln_deps',
      tool,
      findings,
      counts: {
        total: findings.length,
        malicious: findings.filter((f) => f.malicious).length,
        fixable: findings.filter((f) => f.fixed_in.length).length,
        by_severity: bySev,
      },
      warnings,
    };
    console.log(`vuln_deps(ts): ${findings.length} vulns via ${tool} (critical=${bySev.critical}, high=${bySev.high})`);
  }
  fs.writeFileSync(out, JSON.stringify(payload, null, 2));
}

main();
