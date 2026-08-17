"""
ICP Checker - Browser Automation Version (NO API KEY)
------------------------------------------------------
This drives YOUR OWN Chrome browser and YOUR OWN logged-in chatgpt.com
account. It does NOT use the OpenAI API. It literally types each
website into the ChatGPT chat box, one by one, and reads the reply.

SETUP (do this once)
1. Install Python packages:
   pip install selenium webdriver-manager pandas

2. Prepare input_websites.csv in the same folder as this script,
   with one column named exactly: website
       website
       https://example1.com
       https://example2.com

3. Run the script:
       python icp_checker_browser.py

4. A Chrome window will open to chatgpt.com.
   - LOG IN MANUALLY (script waits for you).
   - Once you see the chat box, come back to this terminal and press Enter.

5. The script will then paste your ICP + each website into the chat,
   wait for ChatGPT to finish replying, save the answer, and move to
   the next website — writing progress to output_results.csv as it goes.

NOTES / LIMITS
- This is slower and less stable than the API version, because it
  depends on ChatGPT's web page layout (which can change) and on
  your account's usage limits (free/Plus accounts get rate-limited
  after a number of messages per few hours).
- Do NOT close the Chrome window while it's running.
- If it stalls or ChatGPT layout changed, it prints a warning per row
  and keeps going instead of crashing the whole run.
- Progress is saved after every website, so you can stop (Ctrl+C) and
  resume later — it skips websites already in output_results.csv.
"""

import os
import time
import subprocess
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ---------------- CONFIG ----------------
INPUT_FILE = "input_websites.csv"
OUTPUT_FILE = "output_results.csv"
RESPONSE_WAIT_SECONDS = 45      # max time to wait for ChatGPT to finish answering one website
POLL_INTERVAL = 1.5             # how often to check if ChatGPT finished typing
PAUSE_BETWEEN_WEBSITES = 5      # be gentle, avoid rate limits / detection


def resolve_input_file():
    """Return a CSV that contains a website column.

    The original script expects input_websites.csv, but this workspace already
    contains a workbook named Chromeinfotech OM - Sheet23.csv. When the default
    file is missing, we discover the existing CSV header and reuse it.
    """
    cwd = os.getcwd()
    explicit = os.path.abspath(INPUT_FILE) if INPUT_FILE else ""

    if INPUT_FILE and os.path.exists(explicit):
        return explicit

    preferred = os.path.join(cwd, INPUT_FILE)
    if os.path.exists(preferred):
        return preferred

    for name in sorted(os.listdir(cwd)):
        if not name.lower().endswith(".csv"):
            continue

        path = os.path.join(cwd, name)
        try:
            probe = pd.read_csv(path, nrows=1)
        except Exception:
            continue

        columns = [str(column).strip().lower() for column in probe.columns]
        if "website" in columns:
            return path

    return preferred


ICP_INSTRUCTIONS = """You are a lead qualification assistant. For EACH website I give you, decide if the company matches this Ideal Customer Profile (ICP).

COMPANY CRITERIA (must match):
- Must be a SaaS company with its own software product, SaaS platform, web application, tool, or mobile app.
- The company must own and operate its product (not a reseller, agency, consultancy, or service-only business).
- Employee size: 1-100 employees.
- Company must be headquartered in the United States.

EXCLUSION CRITERIA (disqualify if ANY apply):
- AI companies: AI chatbot platforms, AI agent platforms, generative AI tools, LLM applications, AI assistants, AI automation platforms.
- Financial Services: Banking, FinTech, Insurance, Investment, Lending, Payments, Wealth Management, Accounting.
- Cybersecurity: Network Security, Cloud Security, IAM, Endpoint Security, Threat Intelligence, SIEM, SOC, MSSPs.
- Government or Public Sector: government agencies, public institutions, municipalities, defense organizations, government-owned enterprises.

For every website I send, reply in EXACTLY this format and nothing else:
Answer: Yes
Reason: <one short sentence explaining why this website is a fit>

OR

Answer: No
Reason: <one short sentence explaining why this website is not a fit>

Never reply with "Unclear". Always choose Yes or No directly.

Reply "Ready" if you understand, then wait for me to send websites one at a time."""


def get_chrome_version():
    """Read Chrome file metadata on Windows and return the installed browser version.

    This avoids an old cached ChromeDriver version being paired with a new
    Chrome binary. The metadata comes from the installed executable path.
    """
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_path):
        return None

    try:
        version = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Item '{chrome_path}').VersionInfo.FileVersion",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None

    return version or None


def start_browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=PasswordLeakDetection")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    # Hide automation traces from browser detection layers.
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_path):
        options.binary_location = chrome_path

    # If the caller explicitly provides a Chrome profile root, use it.
    # Otherwise avoid the machine's real Chrome profile directory because it may
    # already be opened by a live browser process, which can make Selenium fail
    # during session creation with 'Chrome instance exited'.
    user_data_dir = os.environ.get("CHROME_USER_DATA_DIR")
    profile_name = os.environ.get("CHROME_PROFILE", "Default")

    if user_data_dir and os.path.exists(user_data_dir):
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_name}")
    else:
        # Fallback for an isolated profile that Selenium can own.
        profile_dir = os.path.join(os.getcwd(), "chrome_profile_icp_checker")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--profile-directory=Default")

    chrome_version = get_chrome_version()
    if chrome_version:
        driver_binary = ChromeDriverManager(driver_version=chrome_version).install()
    else:
        driver_binary = ChromeDriverManager().install()

    driver = webdriver.Chrome(service=Service(driver_binary), options=options)
    return driver


def send_message(driver, text):
    """Send a prompt payload to the current ChatGPT composer.

    ChatGPT's page has shifted between a div-based prompt area and a textarea/
    contenteditable box. This helper tries a small set of observed selectors
    and falls through to the one that actually exists in the live DOM.
    """
    selectors = [
        (By.CSS_SELECTOR, "textarea[data-testid='prompt-textarea']"),
        (By.CSS_SELECTOR, "div#prompt-textarea"),
        (By.CSS_SELECTOR, "textarea"),
        (By.CSS_SELECTOR, "div[contenteditable='true']"),
        (By.CSS_SELECTOR, "div[role='textbox']"),
    ]

    box = None
    for by, selector in selectors:
        try:
            box = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((by, selector))
            )
            break
        except Exception:
            continue

    if box is None:
        raise Exception("Could not locate ChatGPT input box in the current page")

    try:
        box.clear()
    except Exception:
        pass

    box.click()
    for line in text.split("\n"):
        box.send_keys(line)
        box.send_keys(Keys.SHIFT, Keys.ENTER)

    send_button_selectors = [
        (By.CSS_SELECTOR, "button[data-testid='send-button']"),
        (By.CSS_SELECTOR, "button[aria-label='Send']"),
        (By.CSS_SELECTOR, "button[aria-label='Submit']"),
        (By.CSS_SELECTOR, "button[aria-label='Send message']"),
        (By.XPATH, "//button[contains(@aria-label, 'Send')]"),
    ]

    send_button = None
    for by, selector in send_button_selectors:
        try:
            send_button = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((by, selector))
            )
            break
        except Exception:
            continue

    if send_button is not None:
        try:
            send_button.click()
        except Exception:
            try:
                box.send_keys(Keys.ENTER)
            except Exception:
                pass
    else:
        try:
            box.send_keys(Keys.ENTER)
        except Exception:
            pass


def get_latest_response(driver, wait_seconds=RESPONSE_WAIT_SECONDS):
    """Wait until ChatGPT's response stops changing (finished streaming), then return its text.

    ChatGPT's UI may briefly expose a transient assistant status such as
    'Thinking' or 'Ready' while generation is still in progress, and those are
    not whole-answer results. They must be ignored as terminal outputs.
    """
    end_time = time.time() + wait_seconds
    last_text = ""
    stable_count = 0

    while time.time() < end_time:
        time.sleep(POLL_INTERVAL)
        try:
            messages = driver.find_elements(By.CSS_SELECTOR, "div[data-message-author-role='assistant']")
            if not messages:
                continue
            current_text = messages[-1].text.strip()
        except Exception:
            continue

        if not current_text:
            continue

        normalized = current_text.lower().strip()
        if normalized in {"thinking", "ready"}:
            # ChatGPT is still generating the answer or acknowledging the input.
            stable_count = 0
            last_text = ""
            continue

        if current_text == last_text:
            stable_count += 1
            if stable_count >= 2:  # unchanged for 2 polls in a row -> done streaming
                return current_text
        else:
            stable_count = 0
            last_text = current_text

    return last_text  # timed out, return whatever we have


def parse_answer(text):
    """Extract a direct yes/no classification and reason.

    The ICP prompt now requires ChatGPT to return either Answer: Yes or
    Answer: No, and never an 'Unclear' classification. This parser refuses to
    manufacture an 'Unclear' answer and falls back to a direct No only when
    the model response is non-conforming.
    """
    answer, reason = "No", text or ""
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("answer:"):
            val = line.split(":", 1)[1].strip().lower()
            if val.startswith("y"):
                answer = "Yes"
            else:
                answer = "No"
        elif line.lower().startswith("reason:"):
            reason = line.split(":", 1)[1].strip()
    return answer, reason


def main():
    input_path = resolve_input_file()
    if not os.path.exists(input_path):
        print(f"ERROR: Could not find the input CSV. Expected '{INPUT_FILE}' or a CSV with a 'website' column in this folder.")
        return

    df = pd.read_csv(input_path)

    website_column = next(
        (column for column in df.columns if str(column).strip().lower() == "website"),
        None,
    )
    if website_column is None:
        print("ERROR: Input CSV must have a column named 'website'.")
        return

    if website_column != "website":
        df = df.rename(columns={website_column: "website"})

    processed = set()
    results = []
    if os.path.exists(OUTPUT_FILE):
        existing = pd.read_csv(OUTPUT_FILE)
        processed = set(existing["website"].tolist())
        results = existing.to_dict("records")

    driver = start_browser()
    driver.get("https://chatgpt.com/")

    input("\n>>> Log in to ChatGPT in the Chrome window if needed, make sure you see the chat box, then press Enter here to continue...\n")

    print("Sending ICP instructions to ChatGPT...")
    send_message(driver, ICP_INSTRUCTIONS)
    get_latest_response(driver, wait_seconds=30)
    print("ChatGPT is ready. Starting website checks...\n")

    total = len(df)
    for i, row in df.iterrows():
        website = str(row["website"]).strip()
        if not website or website in processed:
            continue

        try:
            send_message(driver, f"Website: {website}")
            reply = get_latest_response(driver)
            answer, reason = parse_answer(reply)
        except Exception as e:
            answer, reason = "Error", str(e)

        results.append({"website": website, "matches_icp": answer, "reason": reason})
        print(f"[{i+1}/{total}] {website} -> {answer}")

        pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
        time.sleep(PAUSE_BETWEEN_WEBSITES)

    print(f"\nDone. Results saved to {OUTPUT_FILE}")
    driver.quit()


if __name__ == "__main__":
    main()