from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

import pandas as pd
import time
import os
import re
import base64
from datetime import datetime

# ---------- TIMER ----------
start_time = time.time()

# ---------- SETUP ----------
options = webdriver.ChromeOptions()

options.add_argument("--start-maximized")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-session-crashed-bubble")
options.add_argument("--disable-infobars")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")
options.add_experimental_option("prefs", {
    "profile.exit_type": "Normal"
})

service = Service(ChromeDriverManager().install())

driver = webdriver.Chrome(service=service, options=options)
driver.maximize_window()
driver.set_page_load_timeout(120)

# ---------- URL LIST ----------
urls = [
    {"url": "https://www.seqrite.com/", "env": "Live"},
    {"url": "https://www.quickhealfoundation.org/", "env": "Live"},
    {"url": "https://www.guardianav.co.in/", "env": "Live"},
    {"url": "https://www.quickheal.co.in/", "env": "Live"},
    {"url": "https://www.quickheal.com/", "env": "Live"},
    {"url": "https://us.quickheal.com/", "env": "Live"},
    {"url": "https://www.quickhealacademy.com/", "env": "Live"},
    {"url": "https://www.quickheal.com/blogs/", "env": "Live"},
    {"url": "https://www.quickheal.co.in/knowledge-centre/", "env": "Live"},
]

# ---------- VARIABLES ----------
results = []
current_date = datetime.now().strftime("%Y-%m-%d")
screenshots_folder = f"screenshots/screenshots_{current_date}"
reports_folder = "reports"
os.makedirs(screenshots_folder, exist_ok=True)
os.makedirs(reports_folder, exist_ok=True)

# ---------- SAVE REPORT ----------
def save_report():
    if not results:
        return
    df = pd.DataFrame(results)
    columns = [
        "Date", "Environment", "URL", "Device",
        "Performance", "Accessibility", "Best Practices", "SEO",
        "FCP", "LCP", "Speed Index", "TBT", "CLS"
    ]
    df = df.reindex(columns=columns)
    report_file = f"{reports_folder}/pagespeed_report_{current_date}.xlsx"
    df.to_excel(report_file, index=False)
    print(f"Report saved: {report_file}")

# ---------- SCREENSHOT ----------
def capture_fullpage(path):
    try:
        print("Preparing full page screenshot...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0,0);")
        time.sleep(3)
        page_height = driver.execute_script("""
            return Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight
            );
        """)
        print(f"Page Height = {page_height}")
        screenshot = driver.execute_cdp_cmd(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True, "fromSurface": True}
        )
        with open(path, "wb") as f:
            f.write(base64.b64decode(screenshot["data"]))
        print(f"Screenshot Saved: {path}")
    except Exception as e:
        print(f"Screenshot failed: {e}")

# ---------- DISMISS COOKIE BANNER ----------
def dismiss_cookie_banner():
    try:
        cookie_xpaths = [
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'got it')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree')]",
        ]
        for xpath in cookie_xpaths:
            try:
                btn = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                driver.execute_script("arguments[0].click();", btn)
                print("Cookie banner dismissed.")
                time.sleep(1)
                return
            except:
                continue
    except:
        pass

# ---------- WAIT FOR REPORT ----------
def wait_for_report_ready(expected_url_fragment, timeout=180):
    """
    THE REAL FIX:
    PageSpeed changes the URL when switching Mobile <-> Desktop.
    Mobile result URL contains: form_factor=mobile  (or no form_factor)
    Desktop result URL contains: form_factor=desktop

    Strategy:
    1. Wait until the browser URL contains expected_url_fragment
    2. Wait until loading indicators disappear
    3. Wait until result elements are present
    4. Extra sleep for all metric values to fully render
    """
    print(f"  Waiting for URL to contain: '{expected_url_fragment}'")

    # Step 1: wait for URL to update to the correct form_factor
    WebDriverWait(driver, timeout).until(
        lambda d: expected_url_fragment in d.current_url
    )
    print(f"  URL confirmed: {driver.current_url}")

    # Step 2: wait for any loading/spinner elements to disappear
    # PageSpeed shows a loading bar / skeleton while Lighthouse runs
    try:
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".lh-header--loading")
            )
        )
    except:
        pass  # element may not exist if loading was already done

    # Step 3: wait for actual result elements
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".lh-gauge__percentage"))
    )
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".lh-metrics-container"))
    )

    print("  Report DOM is ready.")

    # Step 4: buffer for all metric values to fully render
    time.sleep(20)

# ---------- METRICS ----------
def get_metrics():
    script = """
    let data = {
        "Performance":"N/A","Accessibility":"N/A","Best Practices":"N/A","SEO":"N/A",
        "FCP":"N/A","LCP":"N/A","Speed Index":"N/A","TBT":"N/A","CLS":"N/A"
    };
    document.querySelectorAll('.lh-gauge__wrapper').forEach(g=>{
        let label=g.querySelector('.lh-gauge__label')?.innerText;
        let score=g.querySelector('.lh-gauge__percentage')?.innerText;
        if(label && score && data.hasOwnProperty(label)) data[label]=score;
    });
    document.querySelectorAll('.lh-metric').forEach(m=>{
        let title=m.querySelector('.lh-metric__title')?.innerText || "";
        let value=m.querySelector('.lh-metric__value')?.innerText || "";
        if(title.includes("First Contentful Paint")) data["FCP"]=value;
        if(title.includes("Largest Contentful Paint")) data["LCP"]=value;
        if(title.includes("Speed Index")) data["Speed Index"]=value;
        if(title.includes("Total Blocking Time")) data["TBT"]=value;
        if(title.includes("Cumulative Layout Shift")) data["CLS"]=value;
    });
    return data;
    """
    return driver.execute_script(script)

# ---------- EXPAND AUDITS ----------
def expand_audit_sections():
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            txt = btn.text.strip().lower()
            if any(k in txt for k in ["show audits", "show details", "passed audits", "expand view"]):
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                except:
                    pass
    except:
        pass

# ---------- ANALYZE ----------
def analyze_url(url, environment):
    print(f"\nAnalyzing: {url}")

    # ---- MOBILE: navigate directly with form_factor=mobile ----
    encoded_url = url.replace(":", "%3A").replace("/", "%2F")
    mobile_psi_url = f"https://pagespeed.web.dev/report?url={encoded_url}&form_factor=mobile"

    print(f"  Loading Mobile PSI URL: {mobile_psi_url}")
    driver.get(mobile_psi_url)

    # Wait for mobile report
    wait_for_report_ready("form_factor=mobile")

    dismiss_cookie_banner()

    print("Current URL:", driver.current_url)
    driver.save_screenshot(f"{screenshots_folder}/debug_mobile.png")

    filename = re.sub(r'[^a-zA-Z0-9_-]', '_', url)
    expand_audit_sections()
    capture_fullpage(f"{screenshots_folder}/{filename}_mobile.png")

    mobile_data = {
        "Date": current_date,
        "Environment": environment,
        "URL": url,
        "Device": "Mobile",
        **get_metrics()
    }
    results.append(mobile_data)
    print(f"  Mobile Performance: {mobile_data.get('Performance')} | FCP: {mobile_data.get('FCP')} | LCP: {mobile_data.get('LCP')}")
    print("Mobile completed.")

    # ---- DESKTOP: navigate directly with form_factor=desktop ----
    try:
        desktop_psi_url = f"https://pagespeed.web.dev/report?url={encoded_url}&form_factor=desktop"
        print(f"  Loading Desktop PSI URL: {desktop_psi_url}")
        driver.get(desktop_psi_url)

        # Wait for desktop report
        wait_for_report_ready("form_factor=desktop")

        dismiss_cookie_banner()

        driver.save_screenshot(f"{screenshots_folder}/debug_desktop.png")

        expand_audit_sections()
        capture_fullpage(f"{screenshots_folder}/{filename}_desktop.png")

        desktop_data = {
            "Date": current_date,
            "Environment": environment,
            "URL": url,
            "Device": "Desktop",
            **get_metrics()
        }
        results.append(desktop_data)
        print(f"  Desktop Performance: {desktop_data.get('Performance')} | FCP: {desktop_data.get('FCP')} | LCP: {desktop_data.get('LCP')}")
        print("Desktop completed.")

    except Exception as e:
        print(f"Desktop failed: {e}")

    try:
        driver.execute_script("window.localStorage.clear();")
        driver.execute_script("window.sessionStorage.clear();")
    except:
        pass
    driver.delete_all_cookies()

# ---------- MAIN ----------
try:
    total_sites = len(urls)
    print(f"Total Sites: {total_sites}")

    for index, item in enumerate(urls, start=1):
        print(f"\nProcessing {index}/{total_sites}")
        try:
            analyze_url(item["url"], item["env"])
            save_report()
        except Exception as e:
            print(f"Failed: {item['url']}")
            print(type(e))
            print(repr(e))
            results.append({
                "Date": current_date,
                "Environment": item["env"],
                "URL": item["url"],
                "Device": "Error",
                "Performance": "FAILED",
                "Accessibility": "FAILED",
                "Best Practices": "FAILED",
                "SEO": "FAILED",
                "FCP": "FAILED",
                "LCP": "FAILED",
                "Speed Index": "FAILED",
                "TBT": "FAILED",
                "CLS": "FAILED"
            })
            save_report()

finally:
    save_report()
    driver.quit()
    elapsed = round((time.time() - start_time) / 60, 2)
    print("\nCompleted Successfully")
    print(f"Total Records: {len(results)}")
    print(f"Execution Time: {elapsed} minutes")
