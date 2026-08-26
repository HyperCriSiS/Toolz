# Branching workflow

`main` is the single long-lived integration branch.

Use one short-lived branch per logical change / pull request:

- `feature/<name>`
- `fix/<name>`
- `refactor/<name>`
- `test/<name>`
- `docs/<name>`
- `chore/<name>`
- `hotfix/<name>`
- `release/<version>` only for temporary stabilization

Do not create permanent `dev`, `staging`, tool-specific module branches, or feature branches. Independent tools belong in the repository structure, not in permanent Git branches.

Branch from the current `main`, merge back into `main`, then delete the branch. Stacked pull requests are allowed only for genuine temporary dependencies.

Any repository-wide roadmap or planning document must be authoritative on `main`. Mark releases with Git tags rather than permanent release branches.
