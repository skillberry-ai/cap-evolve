# SpreadsheetBench (vendored)

This directory is a filtered `git subtree` of
[RUCKBReasoning/SpreadsheetBench](https://github.com/RUCKBReasoning/SpreadsheetBench),
containing only the harness code (`code_exec_docker/`, `evaluation/`, `inference/`)
used by `templates/adapters/spreadsheetbench/adapter.py` to run and score tasks.

The upstream `data/` and `images/` directories (~136MB of dataset archives and
diagrams) were deliberately excluded via `git filter-repo` before subtree-adding,
so this history never contains those blobs. Dataset files are downloaded at CI
time — see `ci/benchmarks/spreadsheetbench/fetch_data.sh`.

- Upstream repo: https://github.com/RUCKBReasoning/SpreadsheetBench
- License: CC BY SA 4.0 (declared in upstream README.md; upstream has no
  standalone `LICENSE` file as of the commit vendored here)
- Vendored at upstream commit: `0d9dc14` (main)
- Citation:
  ```
  @article{ma2024spreadsheetbench,
    title={SpreadsheetBench: Towards Challenging Real World Spreadsheet Manipulation},
    author={Ma, Zeyao and Zhang, Bohan and Zhang, Jing and Yu, Jifan and Zhang, Xiaokang and Zhang, Xiaohan and Luo, Sijia and Wang, Xi and Tang, Jie},
    journal={arXiv preprint arXiv:2406.14991},
    year={2024}
  }
  ```

## Updating

This was vendored via a filtered scratch clone (to keep upstream's ~136MB of
data/image blobs out of cap-evolve's history entirely), not a raw
`git subtree add` of the upstream repo. To pull upstream changes:

```bash
rm -rf /tmp/sb-upstream
git clone https://github.com/RUCKBReasoning/SpreadsheetBench /tmp/sb-upstream
cd /tmp/sb-upstream
git filter-repo --force \
  --path code_exec_docker --path evaluation --path inference \
  --path README.md --path requirements.txt --path .gitignore
cd -
git subtree pull --prefix=third_party/spreadsheetbench /tmp/sb-upstream main --squash
```
