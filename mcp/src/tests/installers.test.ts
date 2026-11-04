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
import { mkdtempSync, mkdirSync, cpSync, symlinkSync, lstatSync, readlinkSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { installSkill, uninstallTarget, uninstallSkillPath, TARGET_DIRS } from '../installers.js';

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
