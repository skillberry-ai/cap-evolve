#!/usr/bin/env node
// audit-waterfalls.mjs — static waterfall auditor for Next.js API routes and
// async server code. Finds serialized data fetches that could run in parallel,
// including HIDDEN waterfalls that are easy to miss by eye:
//
//   * A dependent call gated behind an INDEPENDENT sibling inside `Promise.all`
//     (e.g. `const [user, config] = await Promise.all([...]); const profile =
//     await fetchProfile(user.id)` — profile waits for `config` for no reason).
//     Wrapping calls in Promise.all does NOT make a route optimal.
//   * Independent calls awaited one after another (classic sequential waterfall).
//   * Blocking side-effect awaits (analytics/logging) before the response.
//
// This is a HEURISTIC linter, not a compiler. Treat every finding as a lead to
// verify by reading the code + measuring, not as a guaranteed bug. It exists so
// you never conclude "this route is already optimal" without checking each
// await barrier against what it actually depends on.
//
// Usage:
//   node <skill>/scripts/audit-waterfalls.mjs [srcDir]     (default: src)
//   node <skill>/scripts/audit-waterfalls.mjs path/to/route.ts [more files...]
//
// Exit code is always 0 (advisory); the report is on stdout.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';

const WORD = (name) => new RegExp(`(^|[^\\w$.])${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`);
const SIDE_EFFECT = /(log|analytic|track|audit|telemetry|metric|report|notify|email|sms|webhook|revalidate)/i;

function collectFiles(target) {
  const out = [];
  let st;
  try { st = statSync(target); } catch { return out; }
  if (st.isFile()) { out.push(target); return out; }
  const skip = new Set(['node_modules', '.next', '.git', 'dist', 'build', 'coverage']);
  const walk = (dir) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      if (e.name.startsWith('.') && e.name !== '.') continue;
      const p = join(dir, e.name);
      if (e.isDirectory()) { if (!skip.has(e.name)) walk(p); }
      else if (['.ts', '.tsx', '.js', '.jsx', '.mjs'].includes(extname(e.name))) out.push(p);
    }
  };
  walk(target);
  return out;
}

// Find the matching close for the bracket that opens at index `open`.
function matchBracket(text, open) {
  const pairs = { '(': ')', '[': ']', '{': '}' };
  const close = pairs[text[open]];
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    const c = text[i];
    if (c === text[open]) depth++;
    else if (c === close) { depth--; if (depth === 0) return i; }
  }
  return text.length - 1;
}

// Extract each `await ...` barrier from a source string, in order.
function extractBarriers(src) {
  const barriers = [];
  const re = /\bawait\b/g;
  let m;
  while ((m = re.exec(src))) {
    const awaitAt = m.index;
    // Capture the statement's RHS: from after `await` to the terminating `;`
    // at bracket-depth 0 (so multi-line Promise.all([...]) is captured whole).
    let i = awaitAt + 5;
    let depth = 0, end = src.length;
    for (; i < src.length; i++) {
      const c = src[i];
      if ('([{'.includes(c)) depth++;
      else if (')]}'.includes(c)) { if (depth === 0) { end = i; break; } depth--; }
      else if (c === ';' && depth === 0) { end = i; break; }
      else if (c === '\n' && depth === 0 && /[)\]}]\s*$/.test(src.slice(awaitAt, i))) { end = i; break; }
    }
    const rhs = src.slice(awaitAt + 5, end);
    // LHS: look back to the start of the statement for `const [a,b] =` / `const x =`.
    const before = src.slice(0, awaitAt);
    const lhsMatch = before.match(/(?:const|let|var)\s*(\[[^\]]*\]|\{[^}]*\}|[A-Za-z_$][\w$]*)\s*=\s*$/);
    let names = [];
    if (lhsMatch) {
      names = (lhsMatch[1].match(/[A-Za-z_$][\w$]*/g) || []).filter((n) => n !== 'const' && n !== 'let' && n !== 'var');
    }
    const line = before.split('\n').length;
    barriers.push({
      line,
      rhs: rhs.trim(),
      names,
      isPromiseAll: /^\s*Promise\.all\b/.test(rhs),
      freshCall: /[A-Za-z_$][\w$.]*\s*\(/.test(rhs),
      assigned: names.length > 0,
    });
    re.lastIndex = end;
  }
  return barriers;
}

function analyze(src) {
  const findings = [];
  const returnIdx = src.search(/\breturn\b/);
  const barriers = extractBarriers(src).filter(
    // Ignore trivial awaits that are not data fetches (e.g. request.json()).
    (b) => b.freshCall && !/^request\.|^req\.|\.json\s*\(\s*\)\s*(\.catch)?/.test(b.rhs)
  );
  const produced = [];
  for (let k = 0; k < barriers.length; k++) {
    const b = barriers[k];
    const refsPrior = produced.filter((p) => WORD(p).test(b.rhs));

    // P1: dependent call gated behind an independent sibling in Promise.all.
    // Look for a PRIOR Promise.all whose result set this barrier only partially
    // uses — the unused siblings needlessly sat on this call's critical path.
    for (let j = 0; j < k; j++) {
      const pj = barriers[j];
      if (!pj.isPromiseAll || pj.names.length < 2) continue;
      const usesSome = pj.names.filter((n) => WORD(n).test(b.rhs));
      const unused = pj.names.filter((n) => !usesSome.includes(n));
      if (usesSome.length >= 1 && unused.length >= 1) {
        findings.push({
          line: b.line,
          kind: 'HIDDEN-WATERFALL',
          msg: `call at line ${b.line} depends only on {${usesSome.join(', ')}} but is awaited AFTER Promise.all([...]) that also produced {${unused.join(', ')}}. It waits for {${unused.join(', ')}} for no reason. Fix: await only its real dependency, then run it in Promise.all with {${unused.join(', ')}}.`,
        });
      }
    }

    // S1: independent call awaited after a prior fetch it does not depend on.
    if (k >= 1 && !b.isPromiseAll && refsPrior.length === 0) {
      findings.push({
        line: b.line,
        kind: 'SEQUENTIAL-WATERFALL',
        msg: `await at line ${b.line} depends on none of the earlier awaited results — it could start in parallel (Promise.all) instead of waiting.`,
      });
    }

    // S2: blocking side-effect (logging/analytics) before the response.
    if (!b.assigned && SIDE_EFFECT.test(b.rhs) && (returnIdx === -1 || src.indexOf(b.rhs) < returnIdx)) {
      findings.push({
        line: b.line,
        kind: 'BLOCKING-SIDE-EFFECT',
        msg: `awaited side-effect at line ${b.line} blocks the response. If its result is not returned, make it non-blocking (Next.js after(), or fire-and-forget).`,
      });
    }

    produced.push(...b.names);
  }
  return findings;
}

const args = process.argv.slice(2);
const targets = args.length ? args : ['src'];
let files = [];
for (const t of targets) files.push(...collectFiles(t));
// Prioritize API routes and server-ish files but still scan everything given.
files = [...new Set(files)];

let total = 0;
for (const f of files) {
  let src;
  try { src = readFileSync(f, 'utf8'); } catch { continue; }
  if (!/\bawait\b/.test(src)) continue;
  const findings = analyze(src);
  if (findings.length) {
    console.log(`\n${f}`);
    for (const fn of findings.sort((a, b) => a.line - b.line)) {
      console.log(`  [${fn.kind}] ${fn.msg}`);
      total++;
    }
  }
}
console.log(`\n${total} potential waterfall issue(s) found across ${files.length} file(s).`);
if (total === 0) console.log('No obvious waterfalls detected — still verify by measuring each API route directly (incl. POST routes).');
