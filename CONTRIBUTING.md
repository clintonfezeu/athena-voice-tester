# Contributing

This repo follows a small, standard trunk-based workflow:

1. Work is tracked as a GitHub **issue**.
2. Each issue is implemented on its own branch, cut from `main`:
   `git checkout -b feat/<short-name>`.
3. Open a **pull request** back into `main` that references the issue
   (`Closes #N`). CI (lint + tests) must pass.
4. Squash-merge (or merge) the PR once green; delete the branch.

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real credentials
```

## Checks before opening a PR

```bash
ruff check bot tests
pytest
```

## Commit style

Conventional, short, imperative: `feat: ...`, `fix: ...`, `docs: ...`,
`test: ...`, `chore: ...`.
