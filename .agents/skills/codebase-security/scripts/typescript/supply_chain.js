#!/usr/bin/env node
/**
 * Layer 6 (TypeScript/JavaScript) — supply-chain hygiene (offline).
 *
 * Checks dependency *declarations* in package.json:
 * - git/http/file: specifiers (bypass the registry, mutable targets)
 * - wildcard versions ("*", "latest", "x")
 * - missing lockfile
 * - typosquat heuristic vs popular npm package names
 * - install scripts (preinstall/postinstall) in direct deps when
 *   node_modules is present — the main npm malware delivery vehicle
 * - overrides/resolutions pointing at URLs
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const POPULAR_NPM = [
  'react', 'react-dom', 'lodash', 'express', 'axios', 'typescript', 'webpack',
  'vite', 'next', 'vue', 'angular', 'jest', 'vitest', 'eslint', 'prettier',
  'chalk', 'commander', 'inquirer', 'dotenv', 'uuid', 'moment', 'dayjs',
  'date-fns', 'zod', 'yup', 'prisma', 'mongoose', 'sequelize', 'knex', 'pg',
  'mysql2', 'redis', 'ioredis', 'socket.io', 'cors', 'helmet', 'passport',
  'jsonwebtoken', 'bcrypt', 'node-fetch', 'undici', 'graphql', 'apollo-server',
  'rxjs', 'styled-components', 'tailwindcss', 'esbuild', 'rollup', 'babel',
  'nodemon', 'ts-node', 'tsx', 'fastify', 'koa', 'nestjs', 'electron',
  'puppeteer', 'playwright', 'cypress', 'storybook', 'svelte', 'astro',
];
const POPULAR_SET = new Set(POPULAR_NPM);

function editDistance1(a, b) {
  if (a === b) return false;
  const la = a.length; const lb = b.length;
  if (Math.abs(la - lb) > 1) return false;
  if (la === lb) {
    let diff = 0;
    for (let i = 0; i < la; i++) if (a[i] !== b[i]) diff++;
    return diff === 1;
  }
  const [s, l] = la < lb ? [a, b] : [b, a];
  let i = 0; let j = 0; let diff = 0;
  while (i < s.length && j < l.length) {
    if (s[i] !== l[j]) { diff++; if (diff > 1) return false; j++; } else { i++; j++; }
  }
  return true;
}

function main() {
  const args = process.argv.slice(2);
  const repo = path.resolve(args[0]);
  const out = args[args.indexOf('--out') + 1];
  fs.mkdirSync(path.dirname(out), { recursive: true });

  const pkgPath = path.join(repo, 'package.json');
  if (!fs.existsSync(pkgPath)) {
    fs.writeFileSync(out, JSON.stringify({
      layer: 'supply_chain', skipped: true, reason: 'no package.json',
      findings: [], counts: { total: 0 },
    }, null, 2));
    console.log('supply_chain(ts): skipped (no package.json)');
    return;
  }
  let pkg;
  try { pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8')); } catch (e) {
    fs.writeFileSync(out, JSON.stringify({
      layer: 'supply_chain', error: true, reason: `package.json unparseable: ${e.message}`,
      findings: [], counts: { total: 0 },
    }, null, 2));
    return;
  }

  const findings = [];
  const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
  const prodDeps = Object.keys(pkg.dependencies || {});

  const hasLockfile = ['package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'bun.lockb', 'bun.lock']
    .some((f) => fs.existsSync(path.join(repo, f)));
  if (!hasLockfile) {
    findings.push({
      package: '(project)', rule: 'missing-lockfile', severity: 'medium',
      message: 'No lockfile — every install resolves fresh versions; supply-chain attacks land silently',
      manifest: 'package.json', tool: 'supply-chain',
      remediation: 'Commit package-lock.json / pnpm-lock.yaml / yarn.lock.',
    });
  }

  for (const [name, spec] of Object.entries(deps)) {
    const specStr = String(spec);
    if (/^(git\+|github:|git:|https?:|file:)/.test(specStr)) {
      const pinned = /#[0-9a-f]{40}$/.test(specStr);
      findings.push({
        package: name, rule: 'url-dependency',
        severity: pinned ? 'low' : 'medium',
        message: `Resolved from \`${specStr.slice(0, 60)}\` instead of the registry${pinned ? ' (commit-pinned)' : ' — target is mutable'}`,
        manifest: 'package.json', tool: 'supply-chain',
        remediation: 'Pin to a full commit SHA or publish to a registry.',
      });
    }
    if (/^(\*|latest|x)$/.test(specStr)) {
      findings.push({
        package: name, rule: 'wildcard-version', severity: hasLockfile ? 'low' : 'medium',
        message: `Version "${specStr}" accepts anything the registry serves`,
        manifest: 'package.json', tool: 'supply-chain',
        remediation: 'Use a semver range (^x.y.z) at minimum.',
      });
    }
    const norm = name.toLowerCase().replace(/^@[^/]+\//, '');
    if (!POPULAR_SET.has(norm)) {
      const hits = POPULAR_NPM.filter((p) => editDistance1(norm, p));
      if (hits.length) {
        findings.push({
          package: name, rule: 'possible-typosquat', severity: 'medium',
          message: `Name is one edit away from popular package(s): ${hits.join(', ')} — verify it is intentional`,
          manifest: 'package.json', tool: 'supply-chain',
          remediation: 'Confirm on npmjs.com this is the package you meant.',
        });
      }
    }
  }

  // Install scripts in direct production deps (needs node_modules present).
  const nm = path.join(repo, 'node_modules');
  let scriptsChecked = false;
  if (fs.existsSync(nm)) {
    scriptsChecked = true;
    for (const name of prodDeps) {
      const depPkgPath = path.join(nm, ...name.split('/'), 'package.json');
      if (!fs.existsSync(depPkgPath)) continue;
      let depPkg;
      try { depPkg = JSON.parse(fs.readFileSync(depPkgPath, 'utf8')); } catch { continue; }
      const scripts = depPkg.scripts || {};
      for (const hook of ['preinstall', 'install', 'postinstall']) {
        if (scripts[hook]) {
          findings.push({
            package: name, rule: 'install-script', severity: 'low',
            message: `Runs \`${hook}\`: ${String(scripts[hook]).slice(0, 80)} — executes arbitrary code at install time`,
            manifest: `node_modules/${name}/package.json`, tool: 'supply-chain',
            remediation: 'Review the script; consider `ignore-scripts=true` in .npmrc with explicit allow-listing.',
          });
        }
      }
    }
  }

  // overrides / resolutions pointing at URLs
  const overrides = JSON.stringify(pkg.overrides || pkg.resolutions || {});
  if (/https?:|git\+|file:/.test(overrides)) {
    findings.push({
      package: '(project)', rule: 'override-url', severity: 'medium',
      message: 'overrides/resolutions replace a package with a URL target',
      manifest: 'package.json', tool: 'supply-chain',
      remediation: 'Pin overrides to registry versions.',
    });
  }

  const bySev = {};
  for (const s of ['high', 'medium', 'low']) bySev[s] = findings.filter((f) => f.severity === s).length;
  const warnings = scriptsChecked ? [] : ['node_modules absent — install-script check skipped (run npm/pnpm install first for full coverage)'];
  const payload = {
    layer: 'supply_chain',
    tool: 'supply-chain',
    declared_dependencies: Object.keys(deps).length,
    has_lockfile: hasLockfile,
    install_scripts_checked: scriptsChecked,
    findings,
    counts: { total: findings.length, ...bySev },
    warnings,
  };
  fs.writeFileSync(out, JSON.stringify(payload, null, 2));
  console.log(`supply_chain(ts): ${findings.length} findings over ${Object.keys(deps).length} declared deps (lockfile=${hasLockfile ? 'yes' : 'no'})`);
}

main();
