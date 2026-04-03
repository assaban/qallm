# T-011: Notebook Adapter Validation Protocol

## Objective

Validate the QALLM notebook adapter and static analysis pipeline against
Li's (2025) MNS dataset of 2,796 Jupyter notebooks from 277 projects.
This validation confirms that:

1. The adapter correctly extracts code cells from real world notebooks
2. Magic commands are stripped without losing actual code
3. Bandit and Radon produce results consistent with Li's published findings
4. The pipeline handles diverse notebook structures without crashing

## Dataset

**Source:** Li, Y. (2025). "User Centered Quality Model and Tool for
Jupyter Notebooks in Research Software." MSc thesis, University of Amsterdam.

**Full dataset:** 2,796 notebooks from 277 projects.

**Validation subset:** 50 notebooks selected across 5 domains and 3 complexity
tiers (simple, moderate, complex), giving a representative sample.

### Selection criteria

| Domain | Simple (1 to 5 code cells) | Moderate (6 to 15 cells) | Complex (16+ cells) |
|--------|---------------------------|-------------------------|-------------------|
| Data science | 3 | 4 | 3 |
| Machine learning | 3 | 4 | 3 |
| Bioinformatics | 3 | 3 | 3 |
| Finance | 3 | 3 | 3 |
| NLP | 3 | 4 | 3 |
| **Subtotal** | **15** | **18** | **15** |

**Total: 48 notebooks** (rounded to ~50 with 2 additional edge cases: one
very large notebook and one with unusual structure).

### Obtaining the dataset

1. Request access from Dr. Zhao or retrieve from the MNS group shared storage
2. Place notebooks in a directory: `data/li_dataset_sample/`
3. Create an input file listing paths: `data/li_dataset_sample/inputs.txt`

```
# data/li_dataset_sample/inputs.txt
# One notebook path per line
data/li_dataset_sample/ds_01_simple.ipynb
data/li_dataset_sample/ds_02_moderate.ipynb
...
```

## Validation procedure

### Step 1: Run the validation script

```bash
python -m qallm.scripts.validate_notebooks \
    --input-file data/li_dataset_sample/inputs.txt \
    --tools bandit radon \
    --json-out validation_results/li_sample_summary.json \
    --csv-out validation_results/li_sample_rows.csv
```

### Step 2: Check the summary

The script outputs a JSON summary with these metrics:

| Metric | Expected | Threshold |
|--------|----------|-----------|
| `extracted_python_success_rate` | 1.0 | Must be 1.0 (all notebooks parse without error) |
| `cell_map_success_rate` | 1.0 | Must be 1.0 (all cell maps generated) |
| `analysis_success_rate` | >= 0.95 | At least 95% of notebooks analyse successfully |
| `ingest_failures` | 0 | No notebooks should fail to ingest |

### Step 3: Spot check findings against Li's results

For a subset of 10 notebooks, manually compare:

| Check | How to verify |
|-------|-------------|
| **Bandit issue count** | Compare QALLM's finding count per notebook against Li's published table. Allow ±20% variance due to tool version differences. |
| **Radon complexity grade** | Compare cyclomatic complexity grades (A through F). Should match exactly or be within one grade. |
| **No false extractions** | Verify that extracted `.py` files contain only actual Python code, no JSON fragments or markdown. |
| **Cell map accuracy** | For 5 notebooks, manually verify that `generated_start_line` in the cell map corresponds to the correct cell in the original notebook. |

### Step 4: Document discrepancies

For any notebook where QALLM results differ significantly from Li's:

1. Record the notebook name, expected result, actual result
2. Categorise the discrepancy:
   * **Tool version difference:** Different Bandit/Radon version flags different rules
   * **Extraction issue:** Adapter missed or mangled code during extraction
   * **Scope difference:** Li's tool analyses raw `.ipynb`; QALLM extracts to `.py` first
3. If extraction issue: file a bug and fix before Cycle 2

## Output artifacts

After running the validation, commit the following to the repo:

```
validation_results/
├── li_sample_summary.json       # Automated summary metrics
├── li_sample_rows.csv           # Per notebook detail rows
└── li_sample_spot_check.md      # Manual spot check notes (10 notebooks)
```

## Success criteria

T-011 is **done** when:

- [ ] 50 notebooks from Li's dataset processed without adapter crashes
- [ ] `extracted_python_success_rate` == 1.0
- [ ] `cell_map_success_rate` == 1.0
- [ ] `analysis_success_rate` >= 0.95
- [ ] Bandit/Radon results are within acceptable variance of Li's findings
- [ ] Discrepancies documented with root cause categories
- [ ] All output artifacts committed to `validation_results/`
