# Job Search Tracker

Nightly LinkedIn job scraper for UK VP/CPO product roles.

## How results are organised

```
results/
  LATEST.md              <- always the most recent run (bookmark this)
  uk_jobs_YYYY-MM-DD.md  <- dated copy
  uk_jobs_YYYY-MM-DD.csv <- CSV for spreadsheet import
```

## One-time setup (required once, < 2 minutes)

The workflow file is ready in `workflow-template.yml`. To activate nightly runs:

### Option A - GitHub UI (no terminal needed)

1. Go to `workflow-template.yml` in this repo
2. Click the pencil (Edit) icon
3. Change the filename at the top from `workflow-template.yml` to `.github/workflows/nightly-scrape.yml`
4. Commit the change

### Option B - Terminal

```bash
git clone https://github.com/prachister-1/Job-search-tracker.git
cd Job-search-tracker
mkdir -p .github/workflows
cp workflow-template.yml .github/workflows/nightly-scrape.yml
git add .github/
git commit -m "Activate nightly workflow"
git push origin main
```

> **Note:** Your GitHub PAT needs the `workflow` scope for this push to succeed.
> Update it at: GitHub -> Settings -> Developer settings -> Personal access tokens
> Then update the `GH_PAT` secret in this repo's Settings -> Secrets -> Actions.

Once activated the workflow runs daily at **06:00 UTC** and commits fresh results automatically.
Trigger manually any time: Actions tab -> "Nightly LinkedIn Job Scraper" -> Run workflow.

## Secrets required

| Secret | Description |
|--------|-------------|
| `APIFY_TOKEN` | Apify API token for LinkedIn scraping |
| `GH_PAT` | GitHub PAT with `repo` + `workflow` scopes |

## Candidate profile targeted

- **Roles:** VP Product, VP Growth Product, CPO, Head of Product (VP-equivalent)
- **Sectors:** Fintech, Payments, Travel, Loyalty, AI, Entertainment, Health, Marketplaces, Subscriptions
- **Location:** UK only
- **Scoring:** 1-10 (8+ = Apply Today, 7 = Consider)
