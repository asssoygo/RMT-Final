# RMT Final — LLM Time-Sensitive Information Benchmark

Authors: Assylkhan Aitzhan, Asylkhan Kozhanov, Amir Nagizkhanov  
Reference date: 2026-11-08

## Study
100 original benchmark questions (90 selected FreshQA + 10 custom), four model families (GPT, Claude, Gemini, Grok), two modes (closed-book and open-book), 800 recorded responses. Original 100 question IDs retained. No responses fabricated, rewritten or deleted to improve accuracy. New retests are exploratory and not a pre-registered paired comparison.

## Run
`python -m pip install matplotlib` (once), then `python evaluate.py`.

## Files
- `benchmark.csv`: original 100 questions, reference answer, URL, verification status.
- `responses.csv`: latest 800 recorded responses.
- `evaluate.py`: the only executable Python program. Regenerates results.
- `prompts/`: conditions for both modes.
- `results/summary.csv`: easy-to-read eight-row model comparison, generated for this snapshot.
- `results/model_results.csv`: full counts, denominators, verified-subset confidence intervals.
- `results/scored_responses.csv`: per-answer labels and reasons.
- `results/review_queue.csv`: records that still need human assessment.
- `results/adjudications.csv`: optional documented manual labels; input to reruns.
- `results/comparison.csv`, `results/statistical_results.csv`: exploratory comparisons and paired tests for classified pairs only.
- `results/*.png`: two comparative plots.

## Meaning of accuracy
`accuracy_on_graded_percent` = Correct / graded answers with supported reference facts. This is **not** validated full 100-question Accuracy, because several reference facts are disputed or unverified and some response classifications are unresolved. Always report the numerator and denominator. `correct_out_of_100_minimum` is the number of already confirmed correct answers out of 100 and is a lower bound. Do not present these as full final accuracy.

## Verification status
93/100 reference items have cited evidence (not necessarily a preserved historical snapshot); 7 remain pending. Questions 405 and 472 were newly source-checked and methodological interpretation recorded directly in benchmark.csv. Other seven questions remain in the benchmark and are not silently omitted. Some short/fuzzy answers require independent review. All 800 answer records were preserved.

## Integrity note
The uploaded candidate titled Claude open-book duplicated the earlier Gemini open-book answers exactly and was **not** adopted as an independent Claude rerun. Source links should be audited; a URL in a model answer does not automatically support its claim. Do not claim the browsing mode caused the entire gain, because model versions, run conditions and retests were not consistently logged.
