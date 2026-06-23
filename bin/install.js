#!/usr/bin/env node
'use strict';
/*
 * Installer for the civ7-modding Claude Code skill.
 * Copies the skill into either the GLOBAL skills dir (~/.claude/skills) or a PROJECT dir
 * (<cwd>/.claude/skills). Pure Node, no dependencies.
 *
 *   npx civ7-modding-skill --global     # available in Claude Code everywhere (default)
 *   npx civ7-modding-skill --project    # only when working in the current folder
 *   npx civ7-modding-skill --dir <path> # install under a custom <path>/.claude/skills
 */
const fs = require('fs');
const os = require('os');
const path = require('path');

const SKILL_NAME = 'civ7-modding';
const PKG_ROOT = path.join(__dirname, '..');
// installer/package machinery that must NOT be copied into the installed skill
const EXCLUDE = new Set(['bin', 'package.json', 'package-lock.json', 'node_modules', '.git', '.gitignore', '.npmignore', 'README.md', 'evals']);

const USAGE = [
  'Install the civ7-modding Claude Code skill.',
  '',
  '  npx civ7-modding-skill --global       install to ~/.claude/skills (default)',
  '  npx civ7-modding-skill --project      install to ./.claude/skills (current folder)',
  '  npx civ7-modding-skill --dir <path>   install to <path>/.claude/skills',
  '',
  'After installing, restart Claude Code (or reload) so it picks up the skill.'
].join('\n');

function parseArgs(argv) {
  const a = { scope: 'global', dir: null, help: false };
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case '--global': case '-g': a.scope = 'global'; break;
      case '--project': case '-p': a.scope = 'project'; break;
      case '--dir': a.dir = argv[++i]; break;
      case '--help': case '-h': a.help = true; break;
    }
  }
  return a;
}

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, e.name);
    const d = path.join(dst, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { console.log(USAGE); return; }

  let base;
  if (args.dir) base = path.join(path.resolve(args.dir), '.claude', 'skills');
  else if (args.scope === 'project') base = path.join(process.cwd(), '.claude', 'skills');
  else base = path.join(os.homedir(), '.claude', 'skills');

  const target = path.join(base, SKILL_NAME);

  // clean install: replace any existing copy so removed files don't linger
  fs.rmSync(target, { recursive: true, force: true });
  fs.mkdirSync(target, { recursive: true });

  for (const e of fs.readdirSync(PKG_ROOT, { withFileTypes: true })) {
    if (EXCLUDE.has(e.name)) continue;
    const s = path.join(PKG_ROOT, e.name);
    const d = path.join(target, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }

  const scopeLabel = args.dir ? `custom (${target})`
    : args.scope === 'project' ? 'project (this folder only)'
    : 'global (everywhere)';
  console.log(`Installed skill '${SKILL_NAME}' -> ${target}`);
  console.log(`Scope: ${scopeLabel}`);
  console.log('Restart Claude Code (or reload) to pick it up. See SKILL.md for what it does.');
}

main();
