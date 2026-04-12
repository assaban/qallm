# T-33: Repair History Snapshots Design

## Problem

The repair service overwrites workspace files in place. After repair, the
original code is lost. This creates three problems:

1. **No comparison.** Users cannot see what changed between repair rounds.
2. **No choice.** Test generation always runs on the latest version; the
   user cannot go back to an earlier or original version.
3. **No data.** The repair progression across rounds is a valuable dataset
   for thesis analysis and potential model training.

## Solution

Add a `repair_history/` directory to the session. Before each repair round
writes changes to the active workspace, snapshot the current workspace state
into `repair_history/round_NN/`. This gives full traceability.

## Session Folder Structure (updated)

```
data/<session-id>/
├── workspace_raw/          # original uploaded/cloned files (never modified)
├── workspace/              # current active version
├── repair_history/         # NEW: snapshots before each repair round
│   ├── round_01/           # workspace state before round 1 repair
│   ├── round_02/           # workspace state before round 2 repair
│   └── ...
├── generated_tests/        # persisted test code per round
├── reports/                # analysis and verification JSON reports
└── session.json
```

## Design Decisions

### 1. Snapshot BEFORE writing, not after

We snapshot the current workspace before repair modifies it. This means:
- `round_01/` contains the **original** code (same as `workspace_raw`)
- `round_02/` contains the code **after round 1 repair**
- The active `workspace/` always contains the latest version

This is simpler than snapshotting after, because the user can always see
"what the code looked like before this round changed it."

### 2. Full directory copy, not individual file diffs

Each snapshot is a complete copy of the workspace. This is slightly
wasteful on disk but makes restoration trivial: just copy the snapshot
back to workspace. Diff-based storage would be more compact but adds
complexity for no practical benefit at thesis scale (typically < 100 files).

### 3. Version selection in interactive CLI

The `qallm full` command's Step 3 (Generate Tests) shows available
versions and lets the user choose which to test:

```
[QALLM] Available code versions:
  [0] Original (workspace_raw)
  [1] After repair round 1
  [2] After repair round 2 (current)

  Generate tests on which version? [2]:
```

### 4. API endpoint for version management

- `GET /api/session/{id}/versions` returns available versions
- `POST /api/session/{id}/restore/{round}` copies a snapshot back to
  active workspace

## Module Changes

| File | Change |
|------|--------|
| `session/workspace.py` | Add `repair_history_dir()`, `snapshot_workspace()`, `list_repair_rounds()`, `restore_repair_round()` |
| `repair/repair_service.py` | Call `snapshot_workspace()` before writing repaired files |
| `cli.py` | Version selection prompt in `cmd_full` before test generation |
| `api/session_routes.py` | Add version listing and restore endpoints |
| `docs/verification-architecture.md` | Update session folder structure |

## Mapping to Thesis

| Thesis element | How repair history helps |
|---------------|------------------------|
| RQ2: static vs static+RL comparison | Run test gen on original AND repaired code, compare results |
| Table 4: Total issues found | Compare static findings across repair rounds |
| Chapter 5: Evaluation | Show repair progression across rounds (Table: findings before/after per round) |
| Future work: model training | Repair history provides labeled before/after pairs |
