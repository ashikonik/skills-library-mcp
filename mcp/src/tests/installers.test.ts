/**
 * The installer path tests.
 *
 * A symlink install replaces the skill *directory* with a link into
 * the library. Getting that path wrong fails silently in two ways:
 *
 *   - the link lands one level too deep (`<dir>/<name>/<name>`), so the
 *     harness never sees the skill at all;
 *   - the uninstall goes through the link and deletes the *library's*
 *     real `SKILL.md` rather than the link.
 *
 * So these tests assert on the link itself: where it is, what it
 * points at, and that removing it leaves the library untouched.
 *
 * They run against a temporary directory, never against the real
 * `~/.puku-cli`.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, cpSync, symlinkSync, lstatSync, readlinkSync, existsSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { installSkill, installAgent, uninstallTarget, uninstallSkillPath, agentTargetPath, TARGET_DIRS } from '../installers.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const BASE = resolve(HERE, '..', '..', '..');

/** A temporary harness directory, with a library copy of one skill. */
function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'skills-library-test-'));
  const skills = join(root, 'skills');
  const lib = join(root, 'library');
  mkdirSync(skills, { recursive: true });
  mkdirSync(lib, { recursive: true });
  cpSync(join(BASE, 'skills', 'tdd-workflow'), join(lib, 'tdd-workflow'), {
    recursive: true,
  });
  // Point the harness at the temporary directory, so these tests never
  // touch the real ~/.puku-cli.
  const original = TARGET_DIRS['puku-cli'];
  TARGET_DIRS['puku-cli'] = [skills];
  return {
    root,
    skills,
    lib,
    restore: () => {
      TARGET_DIRS['puku-cli'] = original;
    },
  };
}

test('a symlink install puts the link at <dir>/<name>', () => {
  const { root, skills, lib, restore } = fixture();
  try {
    const target = installSkill({
      harness: 'puku-cli',
      name: 'tdd-workflow',
      id: 'skill:tdd-workflow',
      description: 'test',
      libPath: 'tdd-workflow',
      skillMdAbs: join(lib, 'tdd-workflow', 'SKILL.md'),
      libraryRoot: lib,
      mode: 'symlink',
      apply: true,
      overwrite: false,
    });

    assert.equal(target.status, 'written');
    const link = join(skills, 'tdd-workflow');
    assert.ok(lstatSync(link).isSymbolicLink(), 'the link is a symlink');
    assert.equal(target.path, link, 'the reported path is the link');
    // Not nested one level deeper.
    assert.ok(!existsSync(join(link, 'tdd-workflow')),
      'the link is not nested inside itself');
    assert.ok(existsSync(join(link, 'SKILL.md')),
      'the link resolves to a real SKILL.md');
    assert.equal(readlinkSync(link), join(lib, 'tdd-workflow'));
  } finally {
    restore();
    rmSync(root, { recursive: true, force: true });
  }
});

test('uninstalling a symlink removes the link, not the library file', () => {
  const { root, skills, lib, restore } = fixture();
  try {
    installSkill({
      harness: 'puku-cli',
      name: 'tdd-workflow',
      id: 'skill:tdd-workflow',
      description: 'test',
      libPath: 'tdd-workflow',
      skillMdAbs: join(lib, 'tdd-workflow', 'SKILL.md'),
      libraryRoot: lib,
      mode: 'symlink',
      apply: true,
      overwrite: false,
    });

    const link = join(skills, 'tdd-workflow');
    const { path, error } = uninstallSkillPath('puku-cli', 'tdd-workflow');
    assert.equal(error, undefined);
    assert.equal(path, link, 'the uninstall path is the link path');

    const r = uninstallTarget(path, true, lib);
    assert.equal(r.status, 'removed');
    assert.ok(!lstatSync(link, { throwIfNoEntry: false }),
      'the link is gone');
    assert.ok(existsSync(join(lib, 'tdd-workflow', 'SKILL.md')),
      "the library's own SKILL.md survived");
  } finally {
    restore();
    rmSync(root, { recursive: true, force: true });
  }
});

test('a dry run writes nothing at all', () => {
  const { root, skills, lib, restore } = fixture();
  try {
    const target = installSkill({
      harness: 'puku-cli',
      name: 'tdd-workflow',
      id: 'skill:tdd-workflow',
      description: 'test',
      libPath: 'tdd-workflow',
      skillMdAbs: join(lib, 'tdd-workflow', 'SKILL.md'),
      libraryRoot: lib,
      mode: 'symlink',
      apply: false,
      overwrite: false,
    });

    assert.equal(target.status, 'planned');
    assert.ok(!lstatSync(join(skills, 'tdd-workflow'), { throwIfNoEntry: false }),
      'nothing was created');
  } finally {
    restore();
    rmSync(root, { recursive: true, force: true });
  }
});

test('AGENTS.md has no path of its own to uninstall', () => {
  const { path, error } = uninstallSkillPath('agentsmd', 'tdd-workflow');
  assert.equal(path, '');
  assert.ok(error && error.includes('shared file'), String(error));
});

// ---------------------------------------------------------------------------
// Agents into puku-cli.
//
// puku-cli reads personal agents from `~/.puku-cli/agents/*.md`. An agent
// whose frontmatter has a `name` but fails validation never loads, so the
// test asserts on the frontmatter that is actually written, not merely on
// the file's existence.
// ---------------------------------------------------------------------------

/** A temporary puku-cli agents directory, with a library copy of one agent. */
function agentFixture() {
  const root = mkdtempSync(join(tmpdir(), 'skills-library-agent-test-'));
  const agents = join(root, 'agents');
  const lib = join(root, 'library');
  mkdirSync(agents, { recursive: true });
  mkdirSync(lib, { recursive: true });
  cpSync(join(BASE, 'agents', 'code-reviewer.md'), join(lib, 'code-reviewer.md'));
  const original = TARGET_DIRS['puku-cli'];
  TARGET_DIRS['puku-cli'] = [join(root, 'skills'), agents];
  return {
    root,
    agents,
    lib,
    restore: () => {
      TARGET_DIRS['puku-cli'] = original;
    },
  };
}

test('agentTargetPath puts a puku-cli agent in the agents directory', () => {
  const { agents, restore } = agentFixture();
  try {
    assert.equal(agentTargetPath('puku-cli', 'code-reviewer'), join(agents, 'code-reviewer.md'));
  } finally {
    restore();
  }
});

test('installing an agent into puku-cli writes frontmatter puku-cli accepts', () => {
  const { root, agents, lib, restore } = agentFixture();
  try {
    const target = installAgent({
      harness: 'puku-cli',
      name: 'code-reviewer',
      id: 'agent:code-reviewer',
      description: 'Reviews code for bugs.',
      agentAbs: join(lib, 'code-reviewer.md'),
      libraryRoot: lib,
      libPath: 'code-reviewer.md',
      installMode: 'copy',
      apply: true,
      overwrite: false,
    });

    assert.equal(target.status, 'written');
    const written = readFileSync(join(agents, 'code-reviewer.md'), 'utf-8');
    assert.ok(written.startsWith('---\n'), 'the file has no frontmatter block');
    assert.ok(/^name:\s*code-reviewer$/m.test(written), 'the frontmatter has no name');
    assert.ok(/^description:\s*Reviews code for bugs\.$/m.test(written),
      'the frontmatter has no description');
  } finally {
    restore();
    rmSync(root, { recursive: true, force: true });
  }
});

test('an agent install into puku-cli is refused outside the agents directory', () => {
  const { root, lib, restore } = agentFixture();
  try {
    const target = installAgent({
      harness: 'puku-cli',
      name: '../../escape',
      id: 'agent:escape',
      description: 'test',
      agentAbs: join(lib, 'code-reviewer.md'),
      libraryRoot: lib,
      libPath: 'code-reviewer.md',
      installMode: 'copy',
      apply: true,
      overwrite: false,
    });

    assert.equal(target.status, 'error');
    assert.equal(target.wall, 'outside_whitelist');
  } finally {
    restore();
    rmSync(root, { recursive: true, force: true });
  }
});

test('a dry run of an agent install writes nothing', () => {
  const { root, agents, lib, restore } = agentFixture();
  try {
    const target = installAgent({
      harness: 'puku-cli',
      name: 'code-reviewer',
      id: 'agent:code-reviewer',
      description: 'test',
      agentAbs: join(lib, 'code-reviewer.md'),
      libraryRoot: lib,
      libPath: 'code-reviewer.md',
      installMode: 'copy',
      apply: false,
      overwrite: false,
    });

    assert.equal(target.status, 'planned');
    assert.ok(!existsSync(join(agents, 'code-reviewer.md')), 'something was created');
  } finally {
    restore();
    rmSync(root, { recursive: true, force: true });
  }
});
