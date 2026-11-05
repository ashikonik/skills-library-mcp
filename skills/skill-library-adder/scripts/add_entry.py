#!/usr/bin/env python3
"""Scaffold a new skill or agent in this library.

This does the *mechanical* half of adding an entry: it creates the
directory or file, writes a valid frontmatter block, and checks the
result against the same rules the scanner uses. What it deliberately
does not do is anything that requires judgement -- naming the domains,
adding the task row, deciding the licence -- and it says so at the end
rather than pretending the entry is finished.

    python3 add_entry.py skill --name my-skill --description "What it does."
    python3 add_entry.py agent --name my-agent --description "What it judges."
    python3 add_entry.py check --path skills/my-skill
    python3 add_entry.py check --path agents/my-agent.md

The checks are the point. A new entry that is scanned but silently
dropped -- a description that is not valid YAML, a name that does not
match its directory, an agent under 200 characters -- looks exactly like
an entry that works, right up until the build and it is simply not
there. So the script fails loudly on those, using the same rules
`.build_library.py` applies.

Nothing here edits a generated document. `ROUTING_GUIDE.md`,
`SKILLS_AND_AGENTS_REPORT.md` and `.library_data.json` are outputs;
editing them is undone by the next build.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))

# The scanner's own rules, restated here so the script can check a
# candidate without importing the builder (which would run it).
#
# `.build_library.py` is a script, not a module -- importing it would
# rebuild the library. So the three rules that decide whether a file is
# taken at all are restated, and they are checked against the builder
# by `.verify_all.py`'s drift test.

# A file shorter than this is not an agent.
AGENT_MIN_CHARS = 200

# The suffixes that make a filename agent-shaped.
AGENT_SUFFIX = ('-reviewer', '-architect', '-resolver', '-planner', '-specialist',
                 '-optimizer', '-explorer', '-evaluator', '-updater', '-cleaner',
                 '-hunter', '-analyst', '-operator', '-harness', '-generator',
                 '-finder', '-packager', '-sanitizer', '-forker', '-troubleshooter',
                 '-staff', '-guide', '-coordinator', '-runner', '-lookup', '-creator',
                 '-verifier', '-auditor', '-critic', '-scorer', '-drafter', '-mapper',
                 '-miner', '-builder', '-researcher', '-loader')

# The directories whose contents are a skill's own supporting files,
# not agents.
COMPANION = {'references', 'rules', 'examples', 'templates', 'assets', 'docs'}

# The files that are documentation whatever they contain.
DOC_FILENAMES = ('readme.md', 'index.md', 'overview.md')

# The keys the line-oriented fallback parser reads.
FM_KEYS = (
    'name', 'description', 'tools', 'model', 'mode', 'permission',
    'license', 'version', 'compatibility', 'metadata', 'origin',
    'allowed-tools', 'disable-model-invocation', 'user-invocable',
    'argument-hint', 'color', 'effort', 'target', 'agents', 'handoffs',
    'tier', 'category', 'tags',
)

NAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')


def frontmatter_block(text):
    """The raw frontmatter block, without the `---` fences."""
    m = re.match(r'^\s*---\s*\n(.*?)\n---', text or '', re.S)
    return m.group(1) if m else ''


def regex_field(raw, key):
    """Read one field with the line-oriented parser.

    This is the fallback the library uses when the YAML does not parse,
    and it is the same parser, so the script checks what the library
    would actually see.
    """
    if not raw:
        return ''
    m = re.search(r'^%s:\s*(.*)$' % re.escape(key), raw, re.M)
    if not m:
        return ''
    v = m.group(1).strip()
    if v in ('>', '|', '>-', '|-'):
        lines = raw.split('\n')
        try:
            i = next(k for k, l in enumerate(lines)
                     if l.startswith(key + ':'))
        except StopIteration:
            return ''
        buf = []
        for l in lines[i + 1:]:
            if l.strip() and not l.startswith(' '):
                break
            buf.append(l.strip())
        return ' '.join(x for x in buf if x).strip('"').strip("'").strip()
    if v.startswith('[') and v.endswith(']'):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('"').strip("'")
                for x in inner.split(',') if x.strip()]
    if len(v) > 1 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v.strip('"').strip("'")


def yaml_parses(raw):
    """(ok, error) -- does this frontmatter block parse as YAML?

    PyYAML when it is available, because that is what the index builder
    uses. Without PyYAML the check cannot be made, and it says so
    rather than pretending.
    """
    try:
        import yaml
    except ImportError:
        return None, 'PyYAML is not installed, so the YAML check was skipped'
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return False, str(e).split('\n')[0]
    if not isinstance(data, dict):
        return False, 'the frontmatter is not a mapping'
    return True, None


def check_skill(path):
    """The rules for a skill directory. Returns a list of problems."""
    problems = []
    notes = []

    skill_md = os.path.join(path, 'SKILL.md')
    if not os.path.isfile(skill_md):
        return ['no SKILL.md in %s' % path], [], '', []

    text = open(skill_md, encoding='utf-8').read()
    raw = frontmatter_block(text)
    if not raw:
        problems.append('no frontmatter block')
        return problems, notes, '', []

    dirname = os.path.basename(os.path.normpath(path))
    name = regex_field(raw, 'name')
    if not name:
        problems.append('no `name:` in the frontmatter -- the directory name '
                        'would be used, and it is better to state it')
    elif name != dirname:
        problems.append('the frontmatter name is %r but the directory is %r '
                        '-- they must match, and the audit fails the build on '
                        'the drift' % (name, dirname))

    desc = regex_field(raw, 'description')
    if not desc:
        problems.append('no `description:` -- search matches on the '
                        'description and on nothing else')
    elif len(desc) < 40:
        notes.append('the description is only %d characters. Say what the '
                     'skill does AND when to use it -- that is the routing '
                     'surface.' % len(desc))

    ok, err = yaml_parses(raw)
    if ok is False:
        problems.append('the frontmatter is not valid YAML: %s\n'
                        '     A plain scalar with an unquoted `:` fails to '
                        'parse, and the fallback reader loses fields.\n'
                        '     Use a block scalar: `description: >`' % err)
    elif ok is None:
        notes.append(err)

    extra = sorted(k for k in FM_KEYS
                   if re.search(r'^%s:' % re.escape(k), raw, re.M))
    unknown = sorted(set(re.findall(r'^([A-Za-z_][\w-]*):', raw, re.M))
                     - set(FM_KEYS))
    if unknown:
        notes.append('these frontmatter keys are not read by the library: %s'
                     % ', '.join(unknown))

    supporting = []
    for dp, dn, fn in os.walk(path):
        dn.sort()
        for f in sorted(fn):
            if f == 'SKILL.md':
                continue
            supporting.append(os.path.relpath(os.path.join(dp, f), path))
    if not supporting:
        notes.append('the skill has no supporting files. That is fine, but a '
                     'skill with a reference file or two is usually a better '
                     'skill.')

    return problems, notes, desc, supporting


def check_agent(path):
    """The rules for an agent file. Returns a list of problems."""
    problems = []
    notes = []

    if not os.path.isfile(path):
        return ['no such file: %s' % path]

    text = open(path, encoding='utf-8').read()
    stem = os.path.basename(path)[:-3]

    if len(text.strip()) < AGENT_MIN_CHARS:
        problems.append('the file is only %d characters. The scanner skips '
                        'anything under %d -- it will not be taken as an '
                        'agent.' % (len(text.strip()), AGENT_MIN_CHARS))

    raw = frontmatter_block(text)
    if not raw:
        problems.append('no frontmatter block')
        return problems, notes, '', False

    name = regex_field(raw, 'name')
    if not name:
        problems.append('no `name:` in the frontmatter. Without one the '
                        'scanner only takes the file if it is in a directory '
                        'named `agents`, or is `mode: subagent`, or ends '
                        '`.agent.md`.')
    elif name != stem:
        problems.append('the frontmatter name is %r but the filename is %r '
                        '-- they must match' % (name, stem))

    desc = regex_field(raw, 'description')
    if not desc:
        problems.append('no `description:` -- search matches on the '
                        'description and on nothing else')
    elif len(desc) < 40:
        notes.append('the description is only %d characters. Say what the '
                     'agent judges AND when to dispatch it.' % len(desc))

    ok, err = yaml_parses(raw)
    if ok is False:
        problems.append('the frontmatter is not valid YAML: %s\n'
                        '     Use a block scalar: `description: >`' % err)
    elif ok is None:
        notes.append(err)

    # The agent-shaped rules. These are the ones that decide whether
    # the file is taken at all, so they are worth checking explicitly.
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    in_agents_dir = parent == 'agents'
    opencode_style = 'mode: subagent' in raw
    vscode_style = stem.endswith('.agent')
    declares_agent = bool(
        re.search(r'^agents:\s*\[', raw, re.M)
        or re.search(r'^agents:\s*$', raw, re.M)
        or re.search(r'^handoffs:\s*$', raw, re.M)
        or re.search(r'^target:\s*\S', raw, re.M))
    suffix_shape = stem.endswith(AGENT_SUFFIX)
    prefix_shape = stem.startswith(('agent', 'code-', 'build-', 'ecc-', 'tdd-'))

    if not (in_agents_dir or opencode_style or vscode_style or declares_agent
            or suffix_shape or prefix_shape):
        problems.append('the scanner would not recognise this file as an '
                        'agent. It needs one of: a directory named `agents`, '
                        '`mode: subagent`, a `.agent.md` filename, an '
                        '`agents:`/`handoffs:`/`target:` key, or a name that '
                        'starts with agent/code-/build-/ecc-/tdd- or ends '
                        'with one of the agent suffixes.')

    if os.path.basename(path).lower() in DOC_FILENAMES:
        problems.append('this filename is treated as documentation whatever '
                        'it contains')

    # The companion check is on the *immediate* parent, not on every
    # component of the absolute path: a library that happens to live
    # under a directory called `docs` is not a skill's reference folder.
    parent_name = os.path.basename(os.path.dirname(os.path.abspath(path)))
    if parent_name in COMPANION:
        problems.append('this file is inside a companion directory '
                        '(references/, rules/, examples/, templates/, assets/, '
                        'docs/), so the scanner treats it as a skill\'s own '
                        'supporting file, not an agent')

    return problems, notes, desc, in_agents_dir


def scaffold_skill(name, description, root, force):
    path = os.path.join(root, name)
    if os.path.exists(path) and not force:
        raise SystemExit('refusing to overwrite %s -- pass --force if that is '
                         'what you want' % path)
    os.makedirs(path, exist_ok=True)

    body = [
        '---',
        'name: %s' % name,
        'description: >',
    ]
    # Fold the description into the block scalar, so the frontmatter is
    # valid YAML whatever the description contains -- including a colon.
    words = description.split()
    line = '  '
    for w in words:
        if len(line) + len(w) + 1 > 76:
            body.append(line.rstrip())
            line = '  '
        line += w + ' '
    if line.strip():
        body.append(line.rstrip())
    body += [
        '---',
        '',
        '# %s' % name.replace('-', ' ').title(),
        '',
        '<!-- Replace this with the skill. Say what it is for, when to reach',
        '     for it, and what it actually does. -->',
        '',
    ]
    with open(os.path.join(path, 'SKILL.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(body))
    return path


def scaffold_agent(name, description, root, model, tools, force):
    path = os.path.join(root, name + '.md')
    if os.path.exists(path) and not force:
        raise SystemExit('refusing to overwrite %s -- pass --force if that is '
                         'what you want' % path)
    os.makedirs(root, exist_ok=True)

    body = [
        '---',
        'name: %s' % name,
        'description: >',
    ]
    words = description.split()
    line = '  '
    for w in words:
        if len(line) + len(w) + 1 > 76:
            body.append(line.rstrip())
            line = '  '
        line += w + ' '
    if line.strip():
        body.append(line.rstrip())
    # The other frontmatter keys go *inside* the block. The closing
    # fence is written last, after them.
    if model:
        body.append('model: %s' % model)
    if tools:
        body.append('tools: [%s]' % ', '.join('"%s"' % t for t in tools))
    body.append('---')
    body += [
        '',
        '# %s' % name.replace('-', ' ').title(),
        '',
        '<!-- Replace this with the agent. Say what it judges, what it looks',
        '     for, and when it should be dispatched. An agent carries',
        '     judgement; a skill carries the method. -->',
        '',
    ]
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(body))
    return path


def report(kind, path, problems, notes, created=False):
    """Print what was checked, what is wrong, and what is left to do."""
    print()
    print('=' * 68)
    print('%s: %s' % (kind, path))
    print('=' * 68)

    if problems:
        print('PROBLEMS -- the scanner will not take this entry as it stands:')
        for p in problems:
            print('  x %s' % p)
    else:
        print('OK -- the scanner will take this entry.')

    if notes:
        print()
        print('notes:')
        for n in notes:
            print('  - %s' % n)

    print()
    if created:
        print('the body is a placeholder -- replace it with the real thing.')
        print()
    print('still to do by hand:')
    if kind == 'skill':
        if created:
            print('  1. write the skill -- the body above is a placeholder')
        else:
            print('  1. check the body says what the skill is for, and when')
            print('     to reach for it')
        print('  2. give it a domain, if its name matches no keyword in')
        print('     mcp/build/domains.py (otherwise it lands in "Other /')
        print('     uncategorised" and ranks as tier 3)')
        print('  3. add a task row to mcp/build/tasks.py if there is a')
        print('     task-shaped question it answers -- that is the strongest')
        print('     router in the system')
        print('  4. add a labelled query to mcp/scripts/eval_search.py so a')
        print('     later change cannot quietly demote it')
    else:
        if created:
            print('  1. write the agent -- the body above is a placeholder')
        else:
            print('  1. check the body says what the agent judges, and when')
            print('     it should be dispatched')
        print('  2. check the name is agent-shaped (the scanner says so above)')
        print('  3. add it to a task row in mcp/build/tasks.py if there is a')
        print('     task-shaped question it judges')
        print('  4. add a labelled query to mcp/scripts/eval_search.py')
    print()
    print('then:')
    print('  ./run.sh                      # the logged build, with validation')
    print('  python3 mcp/scripts/eval_search.py   # did the ranking survive?')
    print()
    print('for the licence and the credits, see references/publishing.md')
    print('for the routing rules, see references/routing.md')
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(
        description='Scaffold a new skill or agent in this library.')
    sub = ap.add_subparsers(dest='command', required=True)

    p = sub.add_parser('skill', help='create a skill directory')
    p.add_argument('--name', required=True)
    p.add_argument('--description', required=True)
    p.add_argument('--root', default=os.path.join(BASE, 'skills'),
                   help='where the skill directory goes')
    p.add_argument('--force', action='store_true')

    p = sub.add_parser('agent', help='create an agent file')
    p.add_argument('--name', required=True)
    p.add_argument('--description', required=True)
    p.add_argument('--root', default=os.path.join(BASE, 'agents'),
                   help='where the agent file goes')
    p.add_argument('--model', default='')
    p.add_argument('--tools', default='',
                   help='comma separated tool allow-list')
    p.add_argument('--force', action='store_true')

    p = sub.add_parser('check', help='check an existing entry')
    p.add_argument('--path', required=True)

    args = ap.parse_args()

    if args.command == 'skill':
        if not NAME_RE.match(args.name):
            raise SystemExit('the name %r is not a usable entry name -- use '
                             'lowercase letters, digits, dots, dashes and '
                             'underscores' % args.name)
        path = scaffold_skill(args.name, args.description, args.root,
                              args.force)
        print('created %s' % path)
        problems, notes, _, _ = check_skill(path)
        return report('skill', path, problems, notes, created=True)

    if args.command == 'agent':
        if not NAME_RE.match(args.name):
            raise SystemExit('the name %r is not a usable entry name -- use '
                             'lowercase letters, digits, dots, dashes and '
                             'underscores' % args.name)
        tools = [t.strip() for t in args.tools.split(',') if t.strip()]
        path = scaffold_agent(args.name, args.description, args.root,
                              args.model, tools, args.force)
        print('created %s' % path)
        problems, notes, _, _ = check_agent(path)
        return report('agent', path, problems, notes, created=True)

    # check
    path = args.path
    if os.path.isdir(path):
        problems, notes, _, _ = check_skill(path)
        return report('skill', path, problems, notes)
    problems, notes, _, _ = check_agent(path)
    return report('agent', path, problems, notes)


if __name__ == '__main__':
    sys.exit(main())
