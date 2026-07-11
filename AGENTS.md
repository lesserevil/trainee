# Agent Instructions

This project is managed by **oompah**. These instructions define the baseline
rules for agents working in this repository. Keep project-specific build,
test, and release details below this section.

<!-- BEGIN OOMPAH TASK INTEGRATION v:2 -->
## Issue Tracking with oompah

This project is managed by **oompah**. The canonical task tracker is oompah's
native Markdown task manager, stored by oompah on the default branch under
`.oompah/tasks`. Do not use TodoWrite, standalone markdown TODO lists, or
direct GitHub issue edits for internal task tracking.

Use the `oompah task` CLI against the running oompah server. The CLI/API keeps
task status, parent/child relationships, dependencies, comments, and
git-backed `.oompah/tasks` files consistent. Humans and agents may inspect
`.oompah/tasks`, but oompah should be the only writer.

### Planning Does Not Require a Task

Design work may be captured in `plans/` without creating a corresponding
oompah task. Plans describe possible approaches, architecture, or future work;
they are not task trackers and do not imply that the work has been accepted or
scheduled.

Create an oompah task when implementation work is accepted or needs status,
ownership, dependencies, or orchestration. A task may link to a plan instead of
copying the plan into task metadata. Checklists in a plan are specification or
acceptance-criteria aids, not task status. The prohibition on standalone
Markdown TODO lists does not prohibit design documents in `plans/`.

### Install the Task CLI

The CLI is distributed from GitHub, not PyPI. The default GitHub install is the
standalone task CLI only; it does not install the oompah service runtime, create
service configuration, or start a local service.

Prefer a release tag when one is available:

```bash
uv tool install "git+https://github.com/lesserevil/oompah@<tag>"
pipx install "git+https://github.com/lesserevil/oompah@<tag>"
```

For unreleased development versions, install from `main`:

```bash
uv tool install "git+https://github.com/lesserevil/oompah"
pipx install "git+https://github.com/lesserevil/oompah"
```

Service operators install the server runtime separately from a cloned oompah
repo with `uv pip install -e '.[server]'` or `make setup`; managed-project
contributors should not need that.

### Server Setup

Point the CLI at the oompah service that manages this project:

```bash
export OOMPAH_SERVER_URL="${OOMPAH_SERVER_URL:-http://127.0.0.1:<port>}"
oompah task --help
oompah task view <task-id>
```

### CLI Quick Reference

```bash
oompah task view <task-id> --project <project-id>
oompah task comment <task-id> --project <project-id> --message "Progress update" --author oompah
oompah task create --project <project-id> --title "Follow-up title" --description "Details"
oompah task child-create <task-id> --project <project-id> --title "Child task title" --description "Details"
oompah task set-dependency <task-id> --project <project-id> --depends-on <other-task-id>
oompah task add-label <task-id> needs:frontend --project <project-id>
oompah task set-status <task-id> Open --project <project-id>
oompah task set-status <task-id> Done --project <project-id> --summary "Completed"
```

### GitHub Issue Intake

GitHub Issues are customer-facing intake, not the internal task graph.

- A customer may open or comment on a GitHub issue.
- Oompah validates the GitHub issue in GitHub and asks for missing information
  there.
- Do not decompose work in GitHub. Do not create GitHub sub-issues for oompah
  decomposition.
- Once intake is sound, oompah creates an internal native Markdown task in
  `Proposed` with metadata referencing the external GitHub issue.
- If the work is too large, oompah decomposes the internal task. The imported
  task becomes the internal epic and child tasks are created under
  `.oompah/tasks`.
- Oompah works and tracks the internal task or epic. On state changes, oompah
  comments on the originating GitHub issue.
- Oompah closes the originating GitHub issue when the internal task reaches
  `Merged` or `Archived`.

GitHub comments are copied into the internal task. Comments made by oompah on
GitHub are not copied back into the internal task, and comments made on
internal tasks are not copied to GitHub except for oompah's status-change
comments.

### Rules

- Search existing oompah tasks before creating follow-up work.
- File follow-up work with `oompah task create --project <project-id>`, not
  GitHub Issues.
- Create decomposition children with `oompah task child-create`; do not
  hand-write parent metadata.
- Record blockers with `oompah task set-dependency`; do not hand-write
  dependency metadata.
- Always pass `--author oompah` when posting progress comments through the CLI.
- Do not edit `.oompah/tasks` files directly unless you are repairing a tracker
  bug and have checked with the project owner.
- Do not edit GitHub `oompah:*`, `type:*`, `priority:*`, `parent:*`, or
  `depends-on:*` labels directly.
## Session Completion

When ending a work session, complete all of these steps:

1. File follow-up tasks with `oompah task create` for remaining work.
2. Run the relevant quality gates for the code you changed.
3. Update the current oompah task status or leave a clear handoff comment.
4. Push all committed work:
   ```bash
   git pull --rebase
   git push
   git status
   ```
5. Verify `git status` reports the branch is up to date with origin.

Work is not complete until the code is pushed and the oompah task is updated.
Never leave finished work only in a local commit.

<!-- END OOMPAH TASK INTEGRATION -->

## Use Makefile Targets

Always use Makefile targets when one exists for the task you are performing.
Before running a raw command, check whether `make help` lists an equivalent
target. Makefile targets encode project-specific flags, setup, and sequencing.

## Documentation Rules

User-facing documentation lives in `docs/`. Design and implementation notes
live in `plans/`. If a doc tells someone what to do with the project, put it
in `docs/`. If it explains how the project works internally or how it might
work in the future, put it in `plans/`.

When creating diagrams in documentation, use Mermaid code blocks.

## Test Coverage Required

Code changes should include focused test coverage. Bug fixes should include a
test that reproduces the failure. Prefer the repository's existing test
patterns and run the relevant Makefile quality gate before handing off.

## Non-Interactive Shell Commands

Use non-interactive command flags in automation so commands do not hang on
prompts. Examples: `cp -f`, `mv -f`, `rm -f`, `rm -rf`, `ssh -o BatchMode=yes`,
and `scp -o BatchMode=yes`.
