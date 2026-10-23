import base64
import os
import re
import sys
import time
from datetime import datetime

import pandas as pd
import requests

API_KEY = os.environ.get("PSI_API_KEY", "").strip()
API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

if not API_KEY:
    sys.exit("PSI_API_KEY is not set. Add it as a GitHub secret (see README).")

start_time = time.time()

# ---------- URL LIST ----------
urls = [
    # Quick Heal India
    {"url": "https://www.quickheal.co.in/", "env": "Live"},
    {"url": "https://www.quickheal.co.in/home-users", "env": "Live"},
    {"url": "https://www.quickheal.co.in/home-users/quick-heal-total-security/", "env": "Live"},
    {"url": "https://www.quickheal.co.in/home-users/quick-heal-internet-security", "env": "Live"},
    {"url": "https://www.quickheal.co.in/home-users/quick-heal-antivirus-pro", "env": "Live"},
    {"url": "https://www.quickheal.co.in/download-free-antivirus", "env": "Live"},
    {"url": "https://www.quickheal.co.in/installer", "env": "Live"},
    {"url": "https://www.quickheal.co.in/quick-heal-product-renew", "env": "Live"},
    {"url": "https://www.quickheal.co.in/multirenew", "env": "Live"},
    # Quick Heal Global
    {"url": "https://www.quickheal.com/", "env": "Live"},
    {"url": "https://www.quickheal.com/blogs/", "env": "Live"},
    {"url": "https://www.quickheal.com/quick-heal-product-renew/", "env": "Live"},
    # Quick Heal US
    {"url": "https://us.quickheal.com/", "env": "Live"},
    {"url": "https://us.quickheal.com/quick-heal-product-renew/", "env": "Live"},
    # Knowledge Centre
    {"url": "https://www.quickheal.co.in/knowledge-centre/", "env": "Live"},
    # Seqrite
    {"url": "https://www.seqrite.com/", "env": "Live"},
    {"url": "https://www.seqrite.com/contact-sales-person/", "env": "Live"},
    {"url": "https://www.seqrite.com/endpoint-protection-cloud/", "env": "Live"},
    # Guardian
    {"url": "https://www.guardianav.co.in/", "env": "Live"},
    {"url": "https://www.guardianav.co.in/renew", "env": "Live"},
    # Foundation
    {"url": "https://www.quickhealfoundation.org/", "env": "Live"},
    # Academy
    {"url": "https://www.quickhealacademy.com/", "env": "Live"},
]

# ---------- FOLDERS ----------
current_date = datetime.now().strftime("%Y-%m-%d")
screenshots_folder = f"screenshots/screenshots_{current_date}"
reports_folder = "reports"
os.makedirs(screenshots_folder, exist_ok=True)
os.makedirs(reports_folder, exist_ok=True)

COLUMNS = [
    "Date", "Environment", "URL", "Device",
    "Performance", "Accessibility", "Best Practices", "SEO",
    "FCP", "LCP", "Speed Index", "TBT", "CLS", "Error",
]
results = []


def save_report():
    if not results:
        return
    df = pd.DataFrame(results).reindex(columns=COLUMNS)
    path = f"{reports_folder}/pagespeed_report_{current_date}.xlsx"
    df.to_excel(path, index=False)
    print(f"Report saved: {path}")


def score(categories, key):
    value = categories.get(key, {}).get("score")
    return round(value * 100) if value is not None else "N/A"


def metric(audits, key):
    return audits.get(key, {}).get("displayValue", "N/A")


def run_psi(url, strategy, retries=3):
    """Call the PageSpeed Insights API with simple retry."""
    params = [
        ("url", url),
        ("strategy", strategy),
        ("key", API_KEY),
        ("category", "performance"),
        ("category", "accessibility"),
        ("category", "best-practices"),
        ("category", "seo"),
    ]
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(API_URL, params=params, timeout=180)
            if r.status_code == 200:
                return r.json()
            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:
            last_error = repr(e)
        print(f"  attempt {attempt}/{retries} failed: {last_error}")
        time.sleep(10 * attempt)
    raise RuntimeError(last_error)


def save_screenshot(lighthouse, path):
    try:
        data = lighthouse["audits"]["final-screenshot"]["details"]["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data.split(",", 1)[1]))
    except Exception as e:
        print(f"  screenshot skipped: {e}")


def analyze(url, env, strategy):
    device = strategy.capitalize()
    print(f"  {device}...")
    data = run_psi(url, strategy)
    lh = data["lighthouseResult"]
    cats, audits = lh["categories"], lh["audits"]

    filename = re.sub(r"[^a-zA-Z0-9_-]", "_", url)
    save_screenshot(lh, f"{screenshots_folder}/{filename}_{strategy}.png")

    row = {
        "Date": current_date, "Environment": env, "URL": url, "Device": device,
        "Performance": score(cats, "performance"),
        "Accessibility": score(cats, "accessibility"),
        "Best Practices": score(cats, "best-practices"),
        "SEO": score(cats, "seo"),
        "FCP": metric(audits, "first-contentful-paint"),
        "LCP": metric(audits, "largest-contentful-paint"),
        "Speed Index": metric(audits, "speed-index"),
        "TBT": metric(audits, "total-blocking-time"),
        "CLS": metric(audits, "cumulative-layout-shift"),
        "Error": "",
    }
    results.append(row)
    print(f"    Perf {row['Performance']} | FCP {row['FCP']} | LCP {row['LCP']}")


# ---------- MAIN ----------
failures = 0
try:
    print(f"Total sites: {len(urls)}")
    for i, item in enumerate(urls, start=1):
        print(f"\n[{i}/{len(urls)}] {item['url']}")
        for strategy in ("mobile", "desktop"):
            try:
                analyze(item["url"], item["env"], strategy)
            except Exception as e:
                failures += 1
                print(f"  FAILED {strategy}: {e}")
                results.append({
                    "Date": current_date, "Environment": item["env"],
                    "URL": item["url"], "Device": strategy.capitalize(),
                    **{c: "FAILED" for c in COLUMNS[4:13]},
                    "Error": str(e)[:300],
                })
            save_report()
            time.sleep(2)
finally:
    save_report()
    elapsed = round((time.time() - start_time) / 60, 2)
    print(f"\nRecords: {len(results)} | Failures: {failures} | Time: {elapsed} min")

# Make the GitHub run go RED if anything failed, so it can't hide again
if failures:
    sys.exit(1)
