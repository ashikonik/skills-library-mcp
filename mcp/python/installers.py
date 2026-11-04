#!/usr/bin/env python3
"""The installers — one per harness, all behind the same safety rules.

A port of `mcp/src/installers.ts`; the two must behave identically.

Three rules hold for every write:

  1. **Dry run by default.** `apply` defaults to `false`; the tool
     returns a plan and writes nothing.
  2. **A path whitelist.** Writes are confined to a fixed set of
     harness directories. Anything outside is refused, not sanitised.
  3. **Symlinks point inward.** A symlink mode always targets a path
     inside the library, never out of it, and `uninstall` refuses to
     remove a symlink whose target is outside the library.

`~/.claude/skills/learned/` is harness-managed and explicitly excluded:
writing into it fights the harness that owns it.
"""
import os
import shutil

from frontmatter import (AGENTSMD_MARKER, AGENTSMD_MARKER_PREFIX, emit_agent,
                         emit_agentsmd_section, emit_openai_agent_yaml,
                         emit_skill, read_body)

HOME = os.path.expanduser('~')

TARGET_DIRS = {
    'claude-code': [os.path.join(HOME, '.claude', 'skills'),
                    os.path.join(HOME, '.claude', 'agents')],
    'codex': [os.path.join(HOME, '.codex', 'skills')],
    'codex-agents': [os.path.join(HOME, '.codex', '.agents', 'skills')],
    'opencode': [os.path.join(HOME, '.config', 'opencode', 'skills'),
                 os.path.join(HOME, '.config', 'opencode', 'agents')],
    'cline': [os.path.join(HOME, '.clinerules')],
    'puku-cli': [os.path.join(HOME, '.puku-cli', 'skills')],
    'agentsmd': [],
}

EXCLUDED_PREFIXES = [os.path.join(HOME, '.claude', 'skills', 'learned')]


def is_inside(base, path):
    """Is `path` inside `base`?"""
    base = os.path.abspath(base)
    path = os.path.abspath(path)
    if base == path:
        return False
    return os.path.commonpath([base, path]) == base


def check_target(harness, target, project_root=None):
    """An error message, or None when the path is allowed."""
    if harness == 'agentsmd':
        bases = [os.path.join(project_root or os.getcwd(), 'AGENTS.md')]
    else:
        bases = TARGET_DIRS.get(harness, [])

    if not bases:
        return "Unsupported harness '%s'." % harness

    resolved = os.path.abspath(target)
    allowed = False
    for b in bases:
        if harness == 'agentsmd':
            if os.path.abspath(b) == resolved:
                allowed = True
        elif is_inside(b, resolved) or os.path.abspath(b) == resolved:
            allowed = True
    if not allowed:
        return ('Refusing to write outside the harness directories: %s' % resolved)

    for ex in EXCLUDED_PREFIXES:
        if is_inside(ex, resolved):
            return ('Refusing to write into the harness-managed directory: %s'
                    % resolved)
    return None


def skill_target_path(harness, name, project_root=None):
    if harness == 'claude-code':
        return os.path.join(TARGET_DIRS['claude-code'][0], name, 'SKILL.md')
    if harness == 'codex':
        return os.path.join(TARGET_DIRS['codex'][0], name, 'SKILL.md')
    if harness == 'codex-agents':
        return os.path.join(TARGET_DIRS['codex-agents'][0], name, 'SKILL.md')
    if harness == 'opencode':
        return os.path.join(TARGET_DIRS['opencode'][0], name, 'SKILL.md')
    if harness == 'cline':
        # Cline rules are flat, numbered files.
        return os.path.join(TARGET_DIRS['cline'][0], '%s.md' % name)
    if harness == 'puku-cli':
        return os.path.join(TARGET_DIRS['puku-cli'][0], name, 'SKILL.md')
    if harness == 'agentsmd':
        return os.path.join(project_root or os.getcwd(), 'AGENTS.md')
    raise ValueError("Unsupported harness '%s'." % harness)


def agent_target_path(harness, name, project_root=None):
    if harness == 'claude-code':
        return os.path.join(TARGET_DIRS['claude-code'][1], '%s.md' % name)
    if harness == 'opencode':
        return os.path.join(TARGET_DIRS['opencode'][1], '%s.md' % name)
    if harness == 'agentsmd':
        return os.path.join(project_root or os.getcwd(), 'AGENTS.md')
    raise ValueError("install_agents is not supported for harness '%s'." % harness)


def uninstall_skill_path(harness, name, project_root=None):
    """Where an installed skill lives on disk, for removal.

    A symlink install replaces the skill *directory* with a link; a
    copy install puts the rewritten `SKILL.md` and the supporting files
    inside that same directory. Removing the directory handles both --
    and a symlink is removed as a link, so the library's own files are
    never touched.

    `AGENTS.md` is shared by many skills, so there is no single path to
    remove; that case is refused with an explanation rather than
    deleting the whole file.
    """
    if harness == 'agentsmd':
        return None, ("AGENTS.md is a shared file, so one skill has no path of "
                      "its own to remove. Delete its section from the file "
                      "instead -- the section is marked "
                      "'<!-- skills-library:%s -->'." % name)
    target = skill_target_path(harness, name, project_root)
    if harness == 'cline':
        # Cline rules are flat files, one per skill.
        return target, None
    return os.path.dirname(target), None


def _copy_bundle(dest_dir, src_dir):
    """Copy the supporting files of a skill alongside its SKILL.md."""
    os.makedirs(dest_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        if name == 'SKILL.md':
            continue
        src = os.path.join(src_dir, name)
        dst = os.path.join(dest_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


def _install_agentsmd_skill(name, id, description, skill_md_abs, target,
                            apply, overwrite):
    """Install one skill as a section in a shared `AGENTS.md`.

    `AGENTS.md` is one file that many skills live in, so the "target
    exists" rule cannot be "the file exists" -- that would refuse the
    second skill. Instead each skill gets a marked section, and the
    file is appended to.
    """
    section = emit_agentsmd_section(name, description,
                                     read_body(skill_md_abs))
    marker = AGENTSMD_MARKER % name

    existing = ''
    if os.path.isfile(target):
        with open(target, encoding='utf-8', errors='replace') as fh:
            existing = fh.read()

    already = marker in existing
    if already and not overwrite:
        return {'harness': 'agentsmd', 'kind': 'skill', 'id': id,
                'name': name, 'path': target, 'action': 'write',
                'status': 'skipped',
                'reason': ('AGENTS.md already has a section for this skill; '
                           'pass overwrite=true to replace it')}

    if not apply:
        return {'harness': 'agentsmd', 'kind': 'skill', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'planned'}

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if already:
            # Replace just this skill's section, leaving the rest of
            # the file -- including other skills' sections -- alone.
            existing = _replace_section(existing, marker, section)
            with open(target, 'w', encoding='utf-8') as fh:
                fh.write(existing)
        else:
            with open(target, 'a', encoding='utf-8') as fh:
                if existing and not existing.endswith('\n'):
                    fh.write('\n')
                fh.write(section)
    except OSError as e:
        return {'harness': 'agentsmd', 'kind': 'skill', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'error',
                'reason': str(e)}

    return {'harness': 'agentsmd', 'kind': 'skill', 'id': id, 'name': name,
            'path': target, 'action': 'write', 'status': 'written',
            'dropped_keys': [], 'sidecars': []}


def _replace_section(text, marker, section):
    """Replace the section starting at `marker` with `section`.

    The section runs until the next marker, or to the end of the file.
    """
    start = text.find(marker)
    if start < 0:
        return text
    rest = text[start + len(marker):]
    nxt = rest.find(AGENTSMD_MARKER_PREFIX)
    end = len(text) if nxt < 0 else start + len(marker) + nxt
    return text[:start] + section + text[end:]


def install_skill(harness, name, id, description, allowed_tools, lib_path,
                  skill_md_abs, library_root, mode='symlink', apply=False,
                  overwrite=False, project_root=None):
    """Install one skill. Returns a target record."""
    target = skill_target_path(harness, name, project_root)
    err = check_target(harness, target, project_root)
    if err:
        return {'harness': harness, 'kind': 'skill', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'error',
                'reason': err}

    # AGENTS.md is a shared file, not one file per skill. It gets its
    # own path through the function: each skill is a marked section,
    # appended, so a second install does not overwrite the first.
    if harness == 'agentsmd':
        return _install_agentsmd_skill(name, id, description, skill_md_abs,
                                       target, apply, overwrite)

    # Cline rules are plain markdown, so a symlink to the library's
    # SKILL.md would carry frontmatter Cline cannot read.
    use_symlink = mode == 'symlink' and harness != 'cline'

    # A symlink replaces the skill *directory*, not the SKILL.md inside
    # it. The directory is what the harness looks for, and linking the
    # whole thing keeps the supporting files in sync too.
    #
    # `target` is `<dir>/<name>/SKILL.md` for every directory-style
    # harness, so the link path is its parent -- NOT `<parent>/<name>`,
    # which would nest the link one level too deep.
    link_path = os.path.dirname(target) if use_symlink else target

    exists = os.path.exists(link_path) or os.path.islink(link_path)
    if exists and not overwrite:
        return {'harness': harness, 'kind': 'skill', 'id': id, 'name': name,
                'path': link_path, 'action': 'symlink' if use_symlink else 'write',
                'status': 'skipped',
                'reason': 'target already exists; pass overwrite=true to replace it'}

    if not apply:
        return {'harness': harness, 'kind': 'skill', 'id': id, 'name': name,
                'path': link_path, 'action': 'symlink' if use_symlink else 'write',
                'status': 'planned'}

    try:
        if use_symlink:
            # Remove the link itself. Removing the file *inside* it would
            # delete the library's real SKILL.md.
            if os.path.islink(link_path):
                os.remove(link_path)
            elif os.path.exists(link_path):
                shutil.rmtree(link_path, ignore_errors=True)
            os.makedirs(os.path.dirname(link_path), exist_ok=True)
            os.symlink(os.path.join(library_root, lib_path), link_path)
            return {'harness': harness, 'kind': 'skill', 'id': id, 'name': name,
                    'path': link_path, 'action': 'symlink', 'status': 'written'}

        if exists:
            os.remove(target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        content, dropped = emit_skill(harness, name, description, allowed_tools)
        body = read_body(skill_md_abs)

        with open(target, 'w', encoding='utf-8') as fh:
            fh.write(content + body)
        sidecars = []
        if harness == 'codex-agents':
            sidecar = os.path.join(os.path.dirname(target), 'agents', 'openai.yaml')
            os.makedirs(os.path.dirname(sidecar), exist_ok=True)
            with open(sidecar, 'w', encoding='utf-8') as fh:
                fh.write(emit_openai_agent_yaml(name, description))
            sidecars.append({'path': sidecar, 'action': 'write', 'status': 'written'})
        try:
            _copy_bundle(os.path.dirname(target), os.path.dirname(skill_md_abs))
        except OSError:
            pass  # a skill with no supporting files is fine
        return {'harness': harness, 'kind': 'skill', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'written',
                'dropped_keys': dropped, 'sidecars': sidecars}
    except OSError as e:
        return {'harness': harness, 'kind': 'skill', 'id': id, 'name': name,
                'path': target, 'action': 'symlink' if use_symlink else 'write',
                'status': 'error', 'reason': str(e)}


def install_agent(harness, name, id, description, tools=None, model='',
                  mode='', agent_abs='', library_root='', lib_path='',
                  install_mode='copy', apply=False, overwrite=False,
                  project_root=None):
    """Install one agent. Returns a target record."""
    if harness == 'cline':
        return {'harness': harness, 'kind': 'agent', 'id': id, 'name': name,
                'path': '', 'action': 'write', 'status': 'error',
                'reason': ("install_agents is not supported for harness 'cline' "
                           "— Cline has no agent mechanism. Use install_skills "
                           "for Cline instead, which writes plain-markdown rules "
                           "to ~/.clinerules/.")}
    target = agent_target_path(harness, name, project_root)
    err = check_target(harness, target, project_root)
    if err:
        return {'harness': harness, 'kind': 'agent', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'error',
                'reason': err}

    exists = os.path.exists(target) or os.path.islink(target)
    if exists and not overwrite:
        return {'harness': harness, 'kind': 'agent', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'skipped',
                'reason': 'target already exists; pass overwrite=true to replace it'}

    if not apply:
        return {'harness': harness, 'kind': 'agent', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'planned'}

    try:
        if exists:
            os.remove(target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        content, dropped = emit_agent(harness, name, description, tools, model, mode)
        body = read_body(agent_abs)
        with open(target, 'w', encoding='utf-8') as fh:
            fh.write(content + body)
        return {'harness': harness, 'kind': 'agent', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'written',
                'dropped_keys': dropped}
    except OSError as e:
        return {'harness': harness, 'kind': 'agent', 'id': id, 'name': name,
                'path': target, 'action': 'write', 'status': 'error',
                'reason': str(e)}


def uninstall_target(target, apply=False, library_root=''):
    """Remove an installed skill or agent.

    A symlink whose target is outside the library is refused: the caller
    may have put something there, and deleting it is not this tool's
    call.
    """
    if not (os.path.exists(target) or os.path.islink(target)):
        return {'status': 'skipped', 'reason': 'nothing installed at that path'}
    if os.path.islink(target):
        link = os.readlink(target)
        abs_target = link if os.path.isabs(link) else os.path.abspath(
            os.path.join(os.path.dirname(target), link))
        if not is_inside(library_root, abs_target):
            return {'status': 'error',
                    'reason': ('Refusing to remove %s: it is a symlink pointing '
                               'outside the library (%s).' % (target, abs_target))}
    if not apply:
        return {'status': 'planned'}
    try:
        if os.path.isdir(target) and not os.path.islink(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        return {'status': 'removed'}
    except OSError as e:
        return {'status': 'error', 'reason': str(e)}
