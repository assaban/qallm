# Contributing to QALLM

## Branching Strategy

```
main          (protected, release quality)
  └── dev     (integration branch, all features merge here first)
       ├── feature/T-xxx-short-name
       ├── feature/T-yyy-short-name
       └── ...
```

### Branch rules

| Branch | Purpose | Who merges | Protection |
|--------|---------|-----------|------------|
| `main` | Stable releases, supervisor demos, thesis snapshots | Merge from `dev` only after CI passes and manual review | Protected: no direct push |
| `dev` | Integration branch, all feature work lands here | Merge from feature branches via PR | CI must pass |
| `feature/T-xxx-*` | One branch per backlog item or small group | Developer works here, opens PR to `dev` | None |

### Workflow

1. **Start work:** Create a feature branch from `dev`
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/T-014-test-generator
   ```

2. **Do the work:** Commit often with descriptive messages
   ```bash
   git add .
   git commit -m "T-014: implement crash oracle test generation"
   ```

3. **Open PR to dev:** Push and create a pull request
   ```bash
   git push origin feature/T-014-test-generator
   gh pr create --base dev --title "T-014: Test generator (one shot baseline)" \
     --milestone "Cycle 2: RL Verification"
   ```

4. **CI checks run automatically.** Ruff lint + pytest must pass.

5. **Merge to dev** once CI is green. Delete the feature branch.

6. **Promote dev to main** at cycle milestones or before supervisor meetings.
   ```bash
   git checkout main
   git merge dev
   git push origin main
   ```

### Commit message format

```
T-xxx: Short description of what changed

Longer explanation if needed. Reference related issues
or decisions. Keep lines under 72 characters.

Closes #issue-number
```

### Naming conventions

| Type | Pattern | Example |
|------|---------|---------|
| Feature branch | `feature/T-xxx-short-name` | `feature/T-014-test-generator` |
| Combined items | `feature/T-xxx-T-yyy-short-name` | `feature/T-011-T-012-adapter-validation` |
| Hotfix | `hotfix/brief-description` | `hotfix/fix-notebook-parser-crash` |

## Running tests locally

```bash
pip install -e ".[dev]"
pytest --tb=short -q
pytest --cov=qallm --cov-report=term-missing
```

## Code style

Ruff handles both linting and formatting. Check before committing:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```
