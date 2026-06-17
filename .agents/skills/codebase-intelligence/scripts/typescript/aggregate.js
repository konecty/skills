#!/usr/bin/env node
// aggregate.js — merges all TypeScript layer JSON results into a single summary
// Usage: node aggregate.js <out_dir> --repo <abs-path>

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// --- arg parsing ---
// First positional arg is out_dir; then --repo <path>
const argv = process.argv.slice(2);
let outDir = null;
let repoPath = null;

// Separate positional args from flags
const positional = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--repo') {
    repoPath = argv[++i];
  } else if (!argv[i].startsWith('--')) {
    positional.push(argv[i]);
  }
}

outDir = positional[0] || null;

if (!outDir || !repoPath) {
  const msg = { lang: 'typescript', error: true, error_message: 'Usage: node aggregate.js <out_dir> --repo <abs-path>' };
  process.stdout.write(JSON.stringify(msg, null, 2) + '\n');
  process.exit(0);
}

const rawDir = path.join(outDir, 'raw', 'typescript');
fs.mkdirSync(rawDir, { recursive: true });

// --- count TS/JS files and LOC ---
let typescriptFiles = 0;
let typescriptLoc = 0;

try {
  const findCmd = [
    'find',
    repoPath,
    '(',
    '-name', '"*.ts"',
    '-o', '-name', '"*.tsx"',
    '-o', '-name', '"*.js"',
    '-o', '-name', '"*.jsx"',
    ')',
    '-not', '-path', '"*/node_modules/*"',
    '-not', '-path', '"*/dist/*"',
    '-not', '-path', '"*/build/*"',
    '-not', '-path', '"*/.next/*"',
    '-not', '-path', '"*/coverage/*"',
  ].join(' ');

  const findOutput = execSync(findCmd, {
    cwd: repoPath,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  const files = findOutput.trim().split('\n').filter(Boolean);
  typescriptFiles = files.length;

  // Count lines with wc -l; feed file list via xargs to handle large repos
  if (files.length > 0) {
    // Write file list to temp file for xargs
    const tmpList = path.join(outDir, '.ts_file_list.tmp');
    try {
      fs.writeFileSync(tmpList, files.join('\n') + '\n');
      const wcOutput = execSync(`xargs wc -l < "${tmpList}"`, {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      // wc -l output: "   42 file.ts\n  100 total\n"
      const totalMatch = wcOutput.match(/(\d+)\s+total/);
      if (totalMatch) {
        typescriptLoc = parseInt(totalMatch[1], 10);
      } else if (files.length === 1) {
        // single file, no "total" line
        const singleMatch = wcOutput.trim().match(/^(\d+)/);
        if (singleMatch) typescriptLoc = parseInt(singleMatch[1], 10);
      }
      fs.unlinkSync(tmpList);
    } catch (e) {
      // fallback: count lines manually for smaller repos
      for (const f of files) {
        try {
          const content = fs.readFileSync(f, 'utf8');
          typescriptLoc += content.split('\n').length;
        } catch (_) {
          // skip unreadable files
        }
      }
    }
  }
} catch (e) {
  // non-fatal — leave counts at 0
}

// --- load layer JSON files ---
const layers = ['dead_code', 'duplication', 'complexity', 'dependencies', 'boundaries', 'hotspots'];
const layerData = {};
const warnings = [];

for (const layer of layers) {
  const layerPath = path.join(rawDir, `${layer}.json`);
  if (!fs.existsSync(layerPath)) {
    warnings.push(`Layer '${layer}' result not found at ${layerPath}`);
    continue;
  }
  try {
    const data = JSON.parse(fs.readFileSync(layerPath, 'utf8'));
    if (data.error) {
      warnings.push(`Layer '${layer}' failed: ${data.error_message}`);
    }
    layerData[layer] = data;
  } catch (e) {
    warnings.push(`Failed to parse layer '${layer}': ${e.message}`);
  }
}

// --- helpers ---
function safeFindings(layer) {
  return (layerData[layer] && !layerData[layer].error && Array.isArray(layerData[layer].findings))
    ? layerData[layer].findings
    : [];
}

function safeCounts(layer) {
  return (layerData[layer] && !layerData[layer].error && layerData[layer].counts)
    ? layerData[layer].counts
    : {};
}

function safeSummary(layer) {
  return (layerData[layer] && !layerData[layer].error && layerData[layer].summary)
    ? layerData[layer].summary
    : {};
}

// --- build summary ---
const deadCounts = safeCounts('dead_code');
const dupCounts = safeCounts('duplication');
const dupSummary = safeSummary('duplication');
const ccCounts = safeCounts('complexity');
const ccSummary = safeSummary('complexity');
const depCounts = safeCounts('dependencies');
const boundsCounts = safeCounts('boundaries');
const hotspotFindings = safeFindings('hotspots');

const topRiskHotspots = hotspotFindings
  .slice(0, 10)
  .map(h => ({ path: h.path, score: h.score }));

// Aggregate hotspot warnings
const hotspotSummary = safeSummary('hotspots');
if (Array.isArray(hotspotSummary.warnings)) {
  for (const w of hotspotSummary.warnings) warnings.push(w);
}

const summary = {
  dead_code_count: (deadCounts.total || 0),
  unused_files: (deadCounts.unused_files || 0),
  unused_exports: (deadCounts.unused_exports || 0),
  duplication_clone_groups: (dupCounts.clone_groups || 0),
  duplicated_lines: (dupCounts.duplicated_lines || 0),
  duplication_rate_pct: dupSummary.duplication_rate_pct || null,
  functions_above_cc_threshold: (ccCounts.above_threshold || 0),
  functions_warn_cc: (ccCounts.warn || 0),
  avg_complexity: ccSummary.avg_complexity || null,
  unused_dependencies: (depCounts.unused || 0),
  unlisted_dependencies: (depCounts.unlisted || 0),
  boundary_violations: (boundsCounts.boundary_violations || 0),
  circular_import_cycles: (boundsCounts.circular_imports || 0),
  hotspots_top_risk: topRiskHotspots,
  warnings,
};

const findings = {
  dead_code: safeFindings('dead_code'),
  duplication: safeFindings('duplication'),
  complexity: safeFindings('complexity'),
  dependencies: safeFindings('dependencies'),
  boundaries: safeFindings('boundaries'),
  hotspots: hotspotFindings,
};

const output = {
  lang: 'typescript',
  typescript_files: typescriptFiles,
  typescript_loc: typescriptLoc,
  summary,
  findings,
};

const aggregatePath = path.join(rawDir, 'aggregate.json');
fs.writeFileSync(aggregatePath, JSON.stringify(output, null, 2));
process.stdout.write(`Wrote aggregate to: ${aggregatePath}\n`);
process.exit(0);
