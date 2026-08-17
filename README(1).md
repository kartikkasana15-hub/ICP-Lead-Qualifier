# ICP Lead Qualifier

A Python automation tool that evaluates company websites against a custom **Ideal Customer Profile (ICP)** and classifies each one as a match or non-match — streamlining B2B lead qualification for weekly outbound delivery.

## What It Does

Instead of manually researching each company website to check whether it fits a target customer profile, this tool automates the process:

1. Reads a list of company websites from a CSV file (`input_websites.csv`).
2. Sends each website, one at a time, to an LLM (via browser automation) along with a fixed ICP prompt.
3. The LLM evaluates the company against defined **inclusion** and **exclusion** criteria.
4. Parses the response into a structured `Yes` / `No` decision with a one-line reason.
5. Saves results incrementally to `output_results.csv`, so the run can be safely stopped and resumed.

## ICP Criteria (example configuration)

**Must match:**
- SaaS company that owns and operates its own software product/platform/app (not a reseller, agency, consultancy, or service-only business)
- 1–100 employees
- Headquartered in the United States

**Excluded if any apply:**
- AI companies (chatbots, AI agents, generative AI tools, LLM apps)
- Financial Services (banking, fintech, insurance, investment, lending, payments, accounting)
- Cybersecurity (network/cloud security, IAM, endpoint security, SIEM, SOC, MSSP)
- Government or Public Sector organizations

*(Criteria are fully configurable in the prompt template — swap in any ICP.)*

## Tech Stack

- **Python** — core scripting and orchestration
- **Selenium + WebDriver Manager** — browser automation with self-healing element detection (falls back across multiple selectors if the target page's layout changes)
- **Pandas** — CSV I/O and data handling

## Key Features

- **Resilient automation** — tries multiple DOM selector strategies so minor UI changes don't break the script
- **Resumable runs** — progress is saved after every website; interrupted runs skip already-processed entries on restart
- **Structured output** — every row includes a clear `Yes`/`No` classification plus a one-sentence reason, ready for CRM import or spreadsheet review
- **No paid API required** — works through a standard logged-in browser session

## Setup

```bash
pip install selenium webdriver-manager pandas
```

1. Set the input and output file paths at the top of the script (`INPUT_FILE` and `OUTPUT_FILE`).

   **Input file:** provide the full path to your existing CSV file:
   ```python
   INPUT_FILE = r"C:\Users\YourName\Desktop\input_websites.csv"
   ```

   **Output file:** provide the path and the output filename you want:
   ```python
   OUTPUT_FILE = r"C:\Users\YourName\Desktop\output_results.csv"
   ```

   You do **not** need to create the output CSV manually. Just enter the desired output path/filename in `OUTPUT_FILE`, and the script will create the file automatically when it runs.

   If you use only a filename, for example:
   ```python
   OUTPUT_FILE = "output_results.csv"
   ```
   the file will be created automatically in the folder from which you run the script.

2. Prepare the input file with a single column named `website`. **CSV format only is supported:**
   ```
   website
   https://example1.com
   https://example2.com
   ```

3. **Close all Chrome windows before running the script.** This is required because the automation starts and controls its own Chrome session. If Chrome is already open, the script may detect the existing Chrome session/process and stop with an error.

4. Run the script from the terminal:
   ```bash
   python icp_checker.py
   ```

5. Log in to your account in the Chrome window that opens, then press Enter in the terminal to continue.
6. The tool works through the list automatically, writing results to the output CSV as it goes — so you can stop (Ctrl+C) and resume later without losing progress.

## Output Format

| website | matches_icp | reason |
|---|---|---|
| https://example1.com | Yes | Owns a SaaS platform, US-based, 40 employees |
| https://example2.com | No | UK-headquartered, disqualifies on location |

## Notes

- **Important:** Close all Chrome windows before starting the script. Leaving Chrome open can cause the browser automation to fail with an error.
- The input CSV must already exist, and `INPUT_FILE` should point to its correct path.
- The output CSV does not need to exist beforehand; the script creates it automatically using the path/filename set in `OUTPUT_FILE`.
- Designed for cases where a paid API isn't available or desired.
- Processing speed is limited by response wait times and rate limits of the underlying chat account.
- Prompt template and exclusion/inclusion criteria can be edited directly in the script to fit any ICP.
