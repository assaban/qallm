# Diagrams

Source files for all thesis figures and presentation visuals.
Each file can be opened directly in a browser (SVG and HTML) or
embedded in LaTeX using `\includegraphics` (SVG) or screenshot (HTML).

## Inventory

| File | Format | Thesis chapter | Description |
|------|--------|---------------|-------------|
| `rl-feedback-loop.svg` | SVG | Ch. 3 Methodology, Ch. 4 Implementation | The five step RL cycle (generate, execute, coverage, score, feedback). Maps to thesis proposal Figure 2. |
| `reward-function-components.svg` | SVG | Ch. 3 Methodology | How ExecutionResult metrics flow through four reward components into a total scalar score. |
| `qallm-complete-pipeline.svg` | SVG | Ch. 4 Implementation | Full QALLM pipeline: input adapters → operations (analyse, repair, verify) → quality report. |
| `adapter-architecture.svg` | SVG | Ch. 4 Implementation | Input adapter pattern: Detector → Factory → Adapter → IngestService → Session workspace. |
| `rl-loop-interactive-example.html` | HTML | Ch. 5 Evaluation, Defence presentation | Interactive round-by-round walkthrough of the RL loop on `compute_mean`. Click each round to see tests, coverage, reward breakdown. |

## How to use in LaTeX

SVG files can be converted to PDF for LaTeX inclusion:

```bash
# Using Inkscape (recommended)
inkscape --export-type=pdf docs/diagrams/rl-feedback-loop.svg

# Or using rsvg-convert
rsvg-convert -f pdf -o rl-feedback-loop.pdf docs/diagrams/rl-feedback-loop.svg
```

Then in LaTeX:

```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=\textwidth]{figures/rl-feedback-loop.pdf}
  \caption{RL-guided test generation feedback loop. The reward function
           (Step 4) scores each round's test quality, and the feedback
           prompt (Step 5) translates the score into natural language
           guidance for the next round.}
  \label{fig:rl-loop}
\end{figure}
```

## How to use the interactive HTML

Open `rl-loop-interactive-example.html` in any browser. No dependencies
or server required. Click each round card to expand details.

For the thesis defence: display it full screen and click through rounds
live to demonstrate how the system improves across iterations.

For the thesis document: take a screenshot of the expanded Round 2 card
(showing the first bug discovery) and use it as a figure.
