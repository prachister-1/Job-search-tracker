#!/usr/bin/env python3
"""LinkedIn job scraper via Apify - UK VP/CPO roles."""

import json, os, re, sys, time, csv
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

APIFY_TOKEN = os.environ['APIFY_TOKEN']
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')

SEARCH_URLS_BATCH1 = [
    "https://www.linkedin.com/jobs/search/?keywords=VP+Product&location=United+Kingdom&geoId=101165590&f_TPR=r604800&f_CS=B%2CC%2CD%2CE%2CF",
    "https://www.linkedin.com/jobs/search/?keywords=Chief+Product+Officer&location=United+Kingdom&geoId=101165590&f_TPR=r604800&f_CS=B%2CC%2CD%2CE%2CF",
    "https://www.linkedin.com/jobs/search/?keywords=VP+Growth+Product&location=United+Kingdom&geoId=101165590&f_TPR=r604800&f_CS=B%2CC%2CD%2CE%2CF",
]

SEARCH_URLS_BATCH2 = [
    "https://www.linkedin.com/jobs/search/?keywords=Head+of+Product+fintech&location=United+Kingdom&geoId=101165590&f_TPR=r604800&f_CS=B%2CC%2CD%2CE%2CF",
    "https://www.linkedin.com/jobs/search/?keywords=VP+Product+travel+loyalty&location=United+Kingdom&geoId=101165590&f_TPR=r604800&f_CS=B%2CC%2CD%2CE%2CF",
    "https://www.linkedin.com/jobs/search/?keywords=VP+Product+AI+health+entertainment&location=United+Kingdom&geoId=101165590&f_TPR=r604800&f_CS=B%2CC%2CD%2CE%2CF",
]

UK_LOCATIONS = [
    'united kingdom', 'london', 'england', 'scotland', 'wales',
    'manchester', 'birmingham', 'bristol', 'edinburgh', 'leeds',
    'liverpool', 'oxford', 'cambridge', 'brighton', 'reading',
    'uk', 'gb', 'great britain', 'nottingham', 'sheffield', 'newcastle',
]

TITLE_INCLUDE = [
    'vp ', 'vp,', 'vice president', 'chief product', 'cpo',
    'head of product', 'group head of product',
]

TITLE_EXCLUDE = [
    'vp engineering', 'vp of engineering', 'vice president engineering',
    'vp sales', 'vp of sales', 'vice president sales',
    'vp marketing', 'vp of marketing', 'vice president marketing',
    'vp legal', 'vp finance', 'vp hr', 'vp people', 'vp operations',
    'vp technology', 'vp infrastructure', 'vp data',
]

SECTOR_KEYWORDS = [
    'fintech', 'payments', 'payment', 'travel', 'loyalty', 'ai ', 'artificial intelligence',
    'entertainment', 'health', 'healthcare', 'marketplace', 'subscription',
    'insurance', 'banking', 'financial', 'ecommerce', 'e-commerce', 'crypto',
    'blockchain', 'gaming', 'media', 'saas consumer', 'retail tech',
]


def apify_post(path: str, body: dict) -> dict:
    url = f'https://api.apify.com/v2{path}?token={APIFY_TOKEN}'
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data,
                                  headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def apify_get(path: str) -> dict:
    url = f'https://api.apify.com/v2{path}?token={APIFY_TOKEN}'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def start_run(urls: list) -> str:
    print(f"  Starting Apify run for {len(urls)} URLs...")
    result = apify_post('/acts/curious_coder~linkedin-jobs-scraper/runs', {
        'urls': urls,
        'count': 60,
        'scrapeCompany': False,
    })
    run_id = result['data']['id']
    print(f"  Run ID: {run_id}")
    return run_id


def poll_run(run_id: str, max_attempts: int = 20) -> dict:
    print(f"  Polling run {run_id}...", flush=True)
    for attempt in range(1, max_attempts + 1):
        info = apify_get(f'/actor-runs/{run_id}')
        status = info['data']['status']
        print(f"  Attempt {attempt}/{max_attempts}: {status}", flush=True)
        if status == 'SUCCEEDED':
            return info['data']
        if status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
            raise RuntimeError(f"Run {run_id} ended with status: {status}")
        time.sleep(30)
    raise RuntimeError(f"Run {run_id} did not complete in time")


def fetch_items(dataset_id: str) -> list:
    url = (f'https://api.apify.com/v2/datasets/{dataset_id}/items'
           f'?token={APIFY_TOKEN}&fields=title,companyName,location,postedAt,salary,link&limit=200')
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def title_passes(title: str) -> bool:
    tl = title.lower()
    if any(ex in tl for ex in TITLE_EXCLUDE):
        return False
    return any(inc in tl for inc in TITLE_INCLUDE)


def location_passes(location: str) -> bool:
    loc = location.lower()
    return any(uk in loc for uk in UK_LOCATIONS)


def score_job(job: dict) -> int:
    title = job.get('title', '').lower()
    company_desc = (job.get('companyName', '') + ' ' + job.get('title', '')).lower()
    posted = job.get('postedAt', '') or ''

    # Base score
    if any(t in title for t in ['vp ', 'vice president', 'chief product', 'cpo']):
        base = 9
    elif 'head of product' in title or 'group head of product' in title:
        base = 8
    elif 'director of product' in title:
        base = 6
    else:
        base = 7

    score = base

    # +1 sector match
    if any(kw in company_desc for kw in SECTOR_KEYWORDS):
        score += 1

    # +1 if posted recently (within 2 days)
    if posted:
        posted_lower = posted.lower()
        if any(x in posted_lower for x in ['hour', '1 day', 'yesterday', 'just now', '2 days']):
            score += 1
        # Handle ISO dates
        try:
            from datetime import date
            posted_date = datetime.fromisoformat(posted.replace('Z', '+00:00'))
            delta = datetime.now(timezone.utc) - posted_date
            if delta.days <= 2:
                score += 1
        except Exception:
            pass

    # -1 if strongly B2B enterprise niche
    b2b_signals = ['enterprise', 'b2b', 'saas b2b', 'hr tech', 'legal tech', 'procurement']
    if any(s in company_desc for s in b2b_signals):
        score -= 1

    return min(10, max(1, score))


def apply_label(score: int) -> str:
    if score >= 8:
        return 'YES'
    if score == 7:
        return 'CONSIDER'
    return 'No'


def deduplicate(jobs: list) -> list:
    seen = set()
    out = []
    for j in jobs:
        key = (j.get('title', '').lower().strip(), j.get('companyName', '').lower().strip())
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


def write_markdown(jobs: list, total_scraped: int, output_path: Path):
    vp_count = len(jobs)
    top_count = sum(1 for j in jobs if j['score'] >= 8)

    lines = [
        f"# UK LinkedIn Job Results - {TODAY}",
        f"**Scraped:** {total_scraped} total | **VP/CPO matches:** {vp_count} | **Score 8+/10:** {top_count}",
        "",
    ]

    top = [j for j in jobs if j['score'] >= 8]
    if top:
        lines += [
            "## Top Roles - Apply Today",
            "",
            "| Rank | Company | Role | Location | Salary | Posted | Score | Apply | Link |",
            "|------|---------|------|----------|--------|--------|-------|-------|------|",
        ]
        for i, j in enumerate(top, 1):
            salary = j.get('salary') or 'Not listed'
            posted = (j.get('postedAt') or 'Unknown')[:20]
            link = j.get('link') or ''
            lines.append(
                f"| {i} | {j['company']} | {j['title']} | {j['location']} "
                f"| {salary} | {posted} | {j['score']}/10 | {j['apply']} | [Apply]({link}) |"
            )
        lines.append("")

    lines += [
        "## All Matches",
        "",
        "| Rank | Company | Role | Location | Salary | Posted | Score | Apply Today | Link |",
        "|------|---------|------|----------|--------|--------|-------|-------------|------|",
    ]
    for i, j in enumerate(jobs, 1):
        salary = j.get('salary') or 'Not listed'
        posted = (j.get('postedAt') or 'Unknown')[:20]
        link = j.get('link') or ''
        lines.append(
            f"| {i} | {j['company']} | {j['title']} | {j['location']} "
            f"| {salary} | {posted} | {j['score']}/10 | {j['apply']} | [Apply]({link}) |"
        )

    lines += [
        "",
        "## Search URLs",
        "",
    ]
    for url in SEARCH_URLS_BATCH1 + SEARCH_URLS_BATCH2:
        lines.append(f"- {url}")

    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"  Written: {output_path}")


def write_csv(jobs: list, output_path: Path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Rank', 'Company', 'Role', 'Location', 'Salary', 'Posted', 'Score', 'Apply Today', 'LinkedIn URL'])
        for i, j in enumerate(jobs, 1):
            w.writerow([
                i, j['company'], j['title'], j['location'],
                j.get('salary') or '', j.get('postedAt') or '',
                j['score'], j['apply'], j.get('link') or ''
            ])
    print(f"  Written: {output_path}")


def main():
    results_dir = Path(__file__).parent.parent / 'results'
    results_dir.mkdir(exist_ok=True)

    print("=== STEP 1: Starting Apify runs ===")
    run1_id = start_run(SEARCH_URLS_BATCH1)
    run2_id = start_run(SEARCH_URLS_BATCH2)

    print("\n=== Polling Batch 1 ===")
    run1_data = poll_run(run1_id)
    dataset1_id = run1_data['defaultDatasetId']

    print("\n=== Polling Batch 2 ===")
    run2_data = poll_run(run2_id)
    dataset2_id = run2_data['defaultDatasetId']

    print("\n=== STEP 2: Fetching results ===")
    items1 = fetch_items(dataset1_id)
    items2 = fetch_items(dataset2_id)
    all_items = items1 + items2
    total_scraped = len(all_items)
    print(f"  Total scraped: {total_scraped}")

    print("\n=== STEP 3: Filter & Score ===")
    filtered = []
    for item in all_items:
        title = item.get('title') or ''
        location = item.get('location') or ''
        if not title_passes(title):
            continue
        if not location_passes(location):
            continue
        score = score_job(item)
        filtered.append({
            'title': title,
            'company': item.get('companyName') or 'Unknown',
            'location': location,
            'salary': item.get('salary') or '',
            'postedAt': item.get('postedAt') or '',
            'link': item.get('link') or '',
            'score': score,
            'apply': apply_label(score),
        })

    filtered = deduplicate(filtered)
    filtered.sort(key=lambda x: x['score'], reverse=True)
    print(f"  Filtered: {len(filtered)} VP/CPO level UK roles")

    print("\n=== STEP 4: Writing files ===")
    dated_md = results_dir / f'uk_jobs_{TODAY}.md'
    latest_md = results_dir / 'LATEST.md'
    dated_csv = results_dir / f'uk_jobs_{TODAY}.csv'

    write_markdown(filtered, total_scraped, dated_md)
    write_markdown(filtered, total_scraped, latest_md)
    write_csv(filtered, dated_csv)

    top5 = filtered[:5]
    scored8 = [j for j in filtered if j['score'] >= 8]

    print("\n=== SUMMARY ===")
    print(f"Run date:       {TODAY}")
    print(f"Jobs scraped:   {total_scraped}")
    print(f"Jobs filtered:  {len(filtered)} (VP/CPO level UK)")
    print(f"Jobs scored 8+: {len(scored8)}")
    print("\nTop 5 roles:")
    for i, j in enumerate(top5, 1):
        print(f"  {i}. {j['company']} | {j['title']} | Score: {j['score']}/10")

    # Write summary to file for Actions step
    summary_path = results_dir / 'run_summary.txt'
    with open(summary_path, 'w') as f:
        f.write(f"DATE={TODAY}\n")
        f.write(f"TOTAL_SCRAPED={total_scraped}\n")
        f.write(f"FILTERED={len(filtered)}\n")
        f.write(f"SCORED_8_PLUS={len(scored8)}\n")


if __name__ == '__main__':
    main()
