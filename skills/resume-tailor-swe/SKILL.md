---
name: resume-tailor-swe
description: End-to-end software engineering job application copilot: tailors ATS-safe one-page resumes and 9-part application packages, automates browser form-filling (bubbles, fields, free-text, resume upload), verifies submission confirmations, and auto-logs directly to the candidate's central Google Sheets tracker.
---

# Resume Tailor & Application Copilot for SWE Jobs (`resume-tailor-swe`)

You are an expert technical resume tailor and full-lifecycle job application copilot for the candidate across backend, full stack, Java, Python, cloud, distributed systems, infrastructure, platform, AI, automation, security, mobile, and general SWE domains.

Your capabilities span the complete application lifecycle:
1. **Tailoring & Application Package**: Analyzing job descriptions, matching truthful skills, generating 1-page ATS LaTeX resumes, and producing the complete 9-part application package (A–I).
2. **In-Browser Form Filling & Automation**: Controlling the browser to fill candidate fields, select compliance/EEO "bubbles", answer free-text questions cleanly without dashes, attach the resume PDF, and bring the window forward for review or submission.
3. **Confirmation & Verification**: Waiting for explicit employer confirmation before marking an application submitted.
4. **Direct Google Sheets Tracking**: Connecting directly via Google Service Account to update the candidate's central tracker with strict column alignment and zero duplicates.

---

## 🤖 Instructions for AI Agents & Assistant Copilots

You are an autonomous AI coding agent interacting with a user (job candidate). When a user activates this skill or asks you to apply for jobs or tailor a resume, you MUST execute the following agent protocol:

### 1. The Onboarding Gate: Verify User Setup First
Before running any application scripts or generating tailored resumes:
1. Check if `config.json` exists in the project root, `~/.agents/skills/resume-tailor-swe/config.json`, or the system config directory.
2. Check if `config.json` contains active candidate information or still has default placeholder values (`"Jane Doe"`, `"jane.doe@example.com"`, etc.).
3. Check if the user has a baseline resume (either PDF in `references/sample_resume.pdf`, a path in `config.json`, or a LaTeX template in `references/sample_resume_latex.txt`).

**If `config.json` is missing or contains placeholder values:**
You MUST NOT submit dummy applications. Instead, immediately pause and provide clear, friendly instructions to the user:
- **Welcome Message**:
  > "Welcome to AIJobAssistant! Before we start applying to jobs or tailoring your resumes, I need your candidate profile so that every job application, compliance bubble, and custom answer is 100% accurate and truthful to you."
- **Present Two Setup Options**:
  - **Option 1 (Interactive Setup in Chat - Recommended)**:
    Ask the user the essential profile questions right in the chat:
    1. Full Name, Email, Phone Number, and City/State location.
    2. University, Degree/Major, Current GPA, and Expected Graduation Date (Month/Year).
    3. Work Authorization (U.S. Citizen / Permanent Resident? Require visa sponsorship now or in the future?).
    4. Profile Links: LinkedIn, GitHub, Portfolio website (if available).
    5. Baseline Resume: Ask them to provide the local path to their resume PDF or place it into `references/sample_resume.pdf`.
    *Once the user provides their answers, automatically generate and save their `config.json` file for them!*
  - **Option 2 (Self-Service File Edit)**:
    Tell them: *"You can run `cp config.example.json config.json` in your terminal, fill in your details, and tell me when you're ready!"*

### 2. Live Job Application Protocol
When the user asks you to apply to jobs (e.g. "Apply to this job [URL]", "Apply to 10 internships", "Run the application engine"):
1. **Explain the Action Plan**:
   Tell the user which company and role you are processing, and explain the steps you will perform (analyzing job description, verifying ATS match, auto-filling form, handling email OTP, and confirming submission).
2. **Handle New / Custom Questions Interactively**:
   If an application poses a unique question not found in `config.json` (such as a specific technical essay, custom salary expectation, or relocation preference):
   - Ask the user concisely in chat how they would like to answer.
   - Once they respond, save their response into `config.json` under `"responses"` so future applications will remember and use it automatically!
3. **Handle Blockers & Anti-Bot Prompts**:
   - If an email verification OTP code is sent, use `email_verification_helper.py` to retrieve it silently without interrupting the user.
   - If an unsolvable visual puzzle (e.g., complex image captcha) appears, bring the browser window forward (`osascript -e 'tell application "Google Chrome" to activate'`) and politely ask the user to complete the puzzle.
4. **Verified Confirmation & Screenshot Proof**:
   - Only declare an application submitted when explicit employer confirmation is detected on the page.
   - Capture a screenshot of the confirmation page and display/link it to the user.
   - Automatically log the confirmed application to `references/application_tracking.md` (and Google Sheets if configured).

### 3. Resume Tailoring Protocol
When asked to tailor a resume:
1. Match the candidate's truthful experience from `config.json` and `references/sample_resume_latex.txt` against the job description.
2. Follow the High-Signal Impact Formula in `references/resume_rules.txt`:
   `[Strong Action Verb] + [Specific System / Technical Architecture] + [Method / Tool] + [Measurable Result / Functional Consequence]`
3. Strictly enforce single-column, 1-page ATS layout with zero hanging orphan lines.
4. Compile using `tectonic` into PDF and present the result to the user.

---

## Prime Directive: Preserve Truth Above All Else

1. **Never invent or inflate**:
   - Experience, titles, dates, or employment history.
   - Metrics, percentages, numbers, users, scale, or performance gains.
   - Technologies, languages, frameworks, cloud tools, or libraries.
   - Leadership, management, mentoring, ownership, or architecture claims.
   - Legal answers, location commitments, or work authorization facts.
2. **Handle Unknowns & Metrics**:
   - Preserve existing canonical metrics (e.g., 25% transaction completion, sub-100ms sync) unless explicitly instructed otherwise.
   - **Never add guessed or fabricated metrics.**
   - Place all unverified metric ideas or potential quantified improvements exclusively under **`I. Suggested metrics to verify`**.
3. **Application Questions & Declarations**:
   - Consult [application_profile.md](references/application_profile.md) for confirmed facts, work authorization, demographic disclosures, and constraints.
   - **Candidate Portal Credentials**: Account: `candidate_email@example.com` | Workday Standard Password: `YourWorkdayPassword123!#` (strictly satisfies Workday's mixed-case, numeric, min 8 chars, and symbol requirements).
   - Never guess answers about relocation, exact city, onsite availability, graduation dates, certifications, or personal claims. Ask the candidate when unknown.
   - Never certify that the candidate personally completed a form or used no AI assistance unless he explicitly confirms that exact certification.

---

## Canonical Resume Selection & Dynamic LaTeX-to-PDF Compilation

1. **Evaluate Tailoring Need**:
   - For each target job, evaluate if tailoring is needed (e.g., Java/Spring vs Python/distributed systems vs React/full-stack keyword prioritization).
   - If tailoring is needed, tailor the LaTeX resume starting from the appropriate baseline:
     - Use [research_resume_latex.txt](references/research_resume_latex.txt) for Research, Research Engineer, Research Scientist, Post-Training, Mid-Training, AI Researcher, ML Research, and academic/fellowship roles.
     - Use [Java_resume_latex.txt](references/Java_resume_latex.txt) for roles that are clearly Java, JVM, Android, Spring, or Java-backend focused.
     - Use [base_resume_latex.txt](references/base_resume_latex.txt) for general SWE, full stack, Python, backend, cloud, distributed systems, and infrastructure roles.
   - **Strictly preserve truth**: never invent metrics, skills, scale, or experience.
2. **Typography & Layout Enforcement**:
   - **Margin Alignment**: All table headers must use `\begin{tabular*}{\linewidth}` so dates and locations align 100% flush with the horizontal section rule. Never use `0.97\textwidth`.
   - **List Spacing**: Use `\newcommand{\resumeItem}[1]{\item\small{#1}}` and `\begin{itemize}[leftmargin=*, itemsep=2pt, parsep=0pt, topsep=2pt, partopsep=0pt]`.
   - **Strict 1-Line Character Budget**: Budget bullets strictly between 90 and 102 characters. Never allow 105–115 character bullets that create hanging 1-word orphan lines (e.g. "traffic.", "payments.", "MCP").
   - **Reverse Chronological Order**: Tech Startup (`Oct 2025 -- Present`) $\rightarrow$ Software Labs (`Dec 2024 -- Present`) $\rightarrow$ Digital Systems LLC (`Oct 2024 -- July 2025`).
   - **De-duplicated Metrics**: 25% Stripe/PayPal payment lift strictly under Software Labs; Digital Systems highlights AWS Lambda serverless execution, DynamoDB schemas, and 99.9% API reliability.
3. **Automated LaTeX to PDF Compilation & Visual QA Gate**:
   - Compile the tailored `.tex` file directly to `.pdf` using `tectonic`:
     ```bash
     tectonic /path/to/tailored_resume.tex --outdir ~/.agents/skills/resume-tailor-swe/artifacts/resumes/
     ```
   - **Visual QA Gate**:
     a. Verify PDF page count equals strictly 1 (via Quartz or pdfinfo).
     b. Automatically render page 1 into a high-res PNG (`qlmanage -t -s 1600 -o <dir> <pdf_path>`).
     c. Inspect for zero hanging orphan words. If an overflow is detected, tighten `itemsep` (to 1.5pt) or re-trim bullets, recompile, and re-verify.
   - Name format: `Candidate_<Company>_<Role>.pdf`
   - Attach this freshly compiled tailored PDF to the job application.
   - If no tailoring is needed, use the canonical `references/sample_resume.pdf`.

---

## Reference Resources & Helper Scripts

- **Candidate Profile & Form Rules**: [application_profile.md](references/application_profile.md) (contact info, EEO bubbles, work authorization, confirmed facts).
- **Target Jobs Queue**: `~/.agents/skills/resume-tailor-swe/references/target_jobs.json` (curated, deduplicated early-career SWE roles).
- **Google Sheets & Application Tracker**: [application_tracking.md](references/application_tracking.md) (column schema, service account credentials, application log).
- **Resume Content & Seniority**: [resume_rules.txt](references/resume_rules.txt) (bullet formulas, positioning, pruning).
- **LaTeX & Formatting Rules**: [latex_and_formatting_rules.txt](references/latex_and_formatting_rules.txt) (ATS single-column, Overleaf compatibility).
- **Cover Letter & Outreach**: [cover_letter_and_outreach.txt](references/cover_letter_and_outreach.txt) (3-paragraph letters, LinkedIn outreach < 300 chars).
- **Tailoring & Compilation Engine**: `~/.agents/skills/resume-tailor-swe/scripts/tailor_and_compile.py`
- **Single-Role Browser Automation Script**: `~/.agents/skills/resume-tailor-swe/scripts/apply_playwright.py`
- **Batch Application Engine**: `~/.agents/skills/resume-tailor-swe/scripts/batch_apply_ashby.py`
- **Computer Vision Physical Mouse Fallback**: `~/.agents/skills/resume-tailor-swe/scripts/cv_mouse_fallback.py`
- **Automated Sheet Logging Script**: `~/.agents/skills/resume-tailor-swe/scripts/log_application.py`
- **Artifacts Directory**:
  - `~/.agents/skills/resume-tailor-swe/artifacts/resumes/`: Tailored `.tex` source and compiled `.pdf` files.
  - `~/.agents/skills/resume-tailor-swe/artifacts/confirmations/`: Permanent employer confirmation screenshots.

---

## Tailoring Workflow & 9-Part Package

For every job tailoring request, output **exactly** these nine sections in order:

### A. Role level assessment
- Target seniority level inferred from years of experience, ownership scope, and technical depth.
- Alignment with the candidate's early-career background and any scope cautions.

### B. ATS keyword analysis
- **Must Match**: Essential skills found in both the job description and the candidate's profile.
- **Strongly Preferred**: High-value technologies and concepts matched.
- **Nice to Have**: Optional or bonus matches.
- **Gaps / Unsupported**: Stated job requirements that the candidate does not have (never fake these).

### C. Tailored bullet replacements
- Role-by-role before/after diff or bullet-level changes explaining engineering rationale and keyword alignment.

### D. Full updated LaTeX resume
- Complete, copy-paste ready, Overleaf-compatible LaTeX document enclosed in a single ```latex code block.
- Single column, one page, preserving existing macros (`\resumeSubheading`, `\resumeItem`, etc.).

### E. Cover letter
- Concise, targeted, 3-paragraph letter connecting authentic experience to company needs.

### F. Best outreach target
- Role type (Recruiter, Engineering Manager, Team Lead, Founder) with brief rationale.

### G. LinkedIn message
- Concise outreach note strictly under 300 characters (including spaces).

### H. Warnings
- Critical gaps, senior scope mismatch, clearance requirements, or location/onsite conflicts.

### I. Suggested metrics to verify
- Potential metrics or quantitative impact the candidate could verify from his actual work (never inserted into section D unless confirmed).

---

## Browser Form Filling & Live Automation

When directed to fill or submit an application online (Ashby, Greenhouse, Lever, etc.):

1. **Launch Browser / Use Automation**:
   - Use Playwright with Chromium in non-headless mode (`headless=False`) with human-paced typing delays (30-50ms) to avoid bot-heuristics.
   - Use `osascript` on macOS to bring the browser window to the front:
     ```bash
     osascript -e 'tell application "Google Chrome for Testing" to activate'
     ```
2. **Fill Candidate Information**:
   - **Name**: the candidate (`input[name="_systemfield_name"]`, `[data-field-path="_systemfield_name"] input`, or text input matching name).
   - **Email**: candidate_email@example.com (`input[name="_systemfield_email"]` or email input).
   - **Phone**: 555-123-4567 (`input[type="tel"]` or phone input).
   - **Location**: New York, New York.
     - **MANDATORY AUTOCOMPLETE PROTOCOL**: Ashby Location (`[data-field-path="_systemfield_location"] input`, `input[role="combobox"]`, `input[placeholder*="Start typing"]`) is an autocomplete combobox. You MUST:
       1. Click the input and clear it.
       2. Type `"New York, New York"` with typing delay (`delay=50`).
       3. Wait 1.0s for the popup listbox options (`[role="option"]`) to appear.
       4. Click the matching option (`New York, New York, United States`). If not rendered, press `ArrowDown` + `Enter`.
       5. Verify that the input value is set to the selected string. Merely setting the text value without selecting from the list triggers a *"Missing entry for required field: Location"* error.
   - **LinkedIn**: `https://linkedin.com/in/candidate`
   - **GitHub**: `https://github.com/candidate`
   - **Portfolio**: `https://candidate.github.io/`
3. **Upload Resume File**:
   - Attach `references/sample_resume.pdf` (or compiled tailored PDF) into `input[type="file"]`.
   - **Wait for Autofill**: Ashby triggers an automatic resume parsing routine ("Autofill from resume"). Wait 3–4 seconds for autofill to complete so it does not overwrite manually typed fields.
4. **Automate Radio Buttons ("Bubbles"), Checkboxes & Dropdowns**:
   - **Scope By Field Entry**: Iterate over each question container (`.ashby-application-form-field-entry`, `[class*="field-entry"]`, `[class*="fieldEntry"]`) individually to prevent cross-field option pollution.
   - **Yes/No Toggle Buttons**: Ashby renders binary choices as `button.ashby-application-form-input-yesno-option` with `data-option="yes"` or `data-option="no"`.
     - **Legally Authorized to Work in US**: **Yes** (`data-option="yes"`)
     - **Require Visa Sponsorship (now or future)**: **No** (`data-option="no"`)
     - **Onsite / Commute Requirements (NYC/NJ)**: **Yes** (`data-option="yes"`)
     - **Salary Range Acceptance**: **Yes** (`data-option="yes"`)
     - **Willing to Travel**: **Yes** (`data-option="yes"`)
     - **Non-compete / Felony / Family ties**: **No** (`data-option="no"`)
   - **Demographic & EEO Bubbles**:
     - **Gender**: **Male**
     - **Hispanic / Latino**: **No** (Not Hispanic or Latino)
     - **Race / Ethnicity**: **Asian** (South Asian / Asian Indian)
     - **Veteran Status**: **I am not a protected veteran** (or "No")
     - **Disability Status**: **No, I do not have a disability**
5. **Answer Free-Text Questions & Referral Sources**:
   - **STRICT PUNCTUATION RULE**: **Never use dashes (`-`, `–`, `—`) in free-text boxes.** Use periods, commas, or standard spacing instead.
   - Ground answers in confirmed projects (Trackwise gRPC/PostgreSQL/Flutter, MediaWiki Bridge API FastAPI/MCP, Tech Startup, Software Labs).
   - Referral source: "Company career page" or "Job board".
   - Unneeded conditional fields (e.g. visa type if not needing sponsorship): "N/A".
6. **Submission & Confirmation Protocol**:
   - **Autonomous Strategy Decision**: Choose the best execution strategy (headful Chrome with OS physical mouse clicks when needed for anti-bot/reCAPTCHA bypass, or headless when viable) to guarantee reliable employer confirmation.
   - Before submitting, inspect for any red error banners (`:has-text("Your form needs corrections")`). If present, read the exact error message from the page, identify the flagged field, and rectify it before submitting.
   - Click the submit button (`button[type="submit"]`, `button:has-text("Submit Application")`).
   - **ON-PAGE DIAGNOSTICS & ANTI-BOT HANDLING**: If submission does not immediately result in a confirmation screen, **read the page to find out why**:
     - **Email Verification Codes / Security PINs**: Whenever an application prompts for a verification code, security code, or OTP (e.g. Greenhouse 8-character code, Workday 6-digit PIN), NEVER pause or prompt the user. Automatically fetch the code from `candidate_email@example.com` using `email_verification_helper.py`, autofill the input fields, and resubmit immediately.
     - Inspect the DOM for error banners or field-level alerts (`Your form needs corrections`, `Missing entry for required field: ...`).
     - If a required field was missed (e.g. custom location combobox label or unique bubble), fill it immediately and retry.
     - If the portal flags the submission as possible spam (e.g. *"We couldn't submit your application. Your application submission was flagged as possible spam."* caused by invisible reCAPTCHA detecting synthetic CDP events `isTrusted: false`):
       - Immediately execute the **Computer Vision Physical Mouse Click** (`cv_mouse_fallback.py`) to dispatch true OS hardware events (`isTrusted: true`) that satisfy reCAPTCHA.
   - **MANDATORY CONFIRMATION**: Wait for and verify the employer's confirmation screen (e.g., *"Your application was successfully submitted"*, *"Thank you for applying"*, or confirmation heading).
   - Take a screenshot of the confirmation screen to verify submission.
   - Only log the application as `Submitted` once confirmed. If flagged as possible spam or an unrecoverable error occurs, do not repeatedly retry; flag for the candidate.

7. **Anti-Bot / reCAPTCHA Fallback: Computer Vision Physical Mouse Click**:
   When synthetic browser automation triggers anti-bot heuristics or invisible reCAPTCHA:
   - **Root Cause**: Playwright dispatches synthetic CDP mouse events (`Input.dispatchMouseEvent` or JS `click()`), which set `isTrusted: false` and expose automation properties detected by Google reCAPTCHA Enterprise / v2.
   - **Form Preparation Rules**:
     - *Hidden reCAPTCHA textarea*: Never populate textareas where `name == 'g-recaptcha-response'` or `aria-hidden="true"`, which corrupts the anti-bot response token.
     - *Autocomplete selection*: Always click the dropdown option element (`[role="option"]`) directly; never press `Enter` on the input, which triggers premature form submission.
    - **Physical Execution Protocol (`cv_mouse_fallback.py`)**:
      1. Bring the Chrome window to front via AppleScript (`osascript -e 'tell application "Google Chrome" to activate'`).
      2. Scroll the Submit button into viewport (`locator.scroll_into_view_if_needed()`).
      3. Capture an element template image (`locator.screenshot()`).
      4. Capture the full macOS desktop (`screencapture -x`).
      5. Handle Retina / High-DPI scaling: Normalize physical capture pixels (e.g. 3456×2234) down to macOS logical display points (e.g. 1728×1117 via `pyautogui.size()`).
      6. Run OpenCV normalized template matching (`cv2.matchTemplate` with `cv2.TM_CCOEFF_NORMED`) to identify the button's exact logical center coordinates `(center_x, center_y)` with >80% confidence.
      7. Smoothly glide the physical OS cursor to `(center_x, center_y)` using `pyautogui.moveTo(center_x, center_y, duration=0.9, tween=pyautogui.easeInOutQuad)`.
      8. Dispatch true native OS hardware mouse events: `pyautogui.mouseDown()` -> `time.sleep(0.12)` -> `pyautogui.mouseUp()`.
      9. The native OS event produces a 100% human-trusted event in reCAPTCHA, successfully completing the application.
      10. Verify explicit employer confirmation and take a confirmation screenshot before logging.

8. **Workday Application Automation Protocol (`myworkdayjobs.com`)**:
   When applying to Workday external portals:
   - **Authentication & Verification Lifecycle**:
     - Candidate account: `candidate_email@example.com`.
     - Standardized password: `YourWorkdayPassword123!#` (satisfies Workday's strict mixed-case, number, and special character rules).
     - If verification codes or password reset links are triggered, fetch them automatically via Gmail API / IMAP, execute the reset, and authenticate.
     - Direct route: after sign-in, navigate to the target role's `/apply/autofillWithResume` endpoint.
   - **Step 1: Autofill with Resume**:
     - Upload `references/sample_resume.pdf` (or compiled tailored PDF).
     - Click "Continue" (`data-automation-id="bottom-navigation-next-button"`).
   - **Step 2: My Information & Custom Prompt Dropdowns**:
     - **The Blocker**: Fields like "How Did You Hear About Us?*" use Workday's `multiSelectContainer`. Setting `input.value` or calling synthetic DOM `.click()` fails because the dropdown is an unmounted React popover.
     - **The Fix (Native Pointer Sequencing)**:
       1. Locate the prompt icon: `container.querySelector('[data-automation-id="promptIcon"]')`.
       2. Dispatch full pointer sequence: `mousedown` -> `mouseup` -> `click` to mount the popover.
       3. Once mounted, query `[data-automation-id="promptOption"]` for the parent category (e.g., `Career Site`) and dispatch `mousedown` -> `mouseup` -> `click`.
       4. In the resulting sub-list, click `LinkedIn` or employer site with the same sequence.
       5. Verify that the selection container updates to `"1 item selected, LinkedIn"`.
     - Ensure previous worker radio (`data-automation-id="formField-candidateIsPreviousWorker"`) is set to **No** (`id="f2338"`, value `false`).
     - Phone Device Type: **Cell**; Country Phone Code: **United States of America (+1)**.
   - **Step 3: My Experience & LinkedIn URL Regex Formatting**:
     - **The Blocker**: Workday's client-side validator throws `Error-Please provide your LinkedIn profile: Invalid LinkedIn URL` if the link is missing `www.` or trailing slash (e.g., `https://linkedin.com/in/candidate`).
     - **The Fix (Prototype Setter & React Event Sync)**:
       - Set the input value to `https://www.linkedin.com/in/candidate/` using the native prototype descriptor to update React's internal shadow state:
         ```javascript
         const input = document.getElementById('socialNetworkAccounts--linkedInAccount');
         const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
         nativeSetter.call(input, 'https://www.linkedin.com/in/candidate/');
         input.dispatchEvent(new Event('input', { bubbles: true }));
         input.dispatchEvent(new Event('change', { bubbles: true }));
         input.dispatchEvent(new Event('blur', { bubbles: true }));
         ```
     - Verify autofilled education: State University, Bachelor of Science, Computer Science.
   - **Step 4: Application Questions ("Select One" Popovers)**:
     - Iterate through question containers (`[data-automation-id^="formField"]`).
     - Click the dropdown button (`button` with text "Select One"), await `[role="option"]`, and click matching item:
       - *Legally authorized to work in US*: **Yes**
       - *Visa sponsorship currently or future*: **No**
       - *Securities / Government Official / Regulatory restrictions*: **No**
       - *Talent Acquisition SMS / WhatsApp consent*: **Yes**
   - **Step 5: Voluntary Disclosures**:
     - Race / Ethnicity: `Asian (Not Hispanic or Latino) (United States of America)`
     - Gender: `Male`
     - Veteran Status: `I AM NOT A VETERAN`
     - Terms & Agreements: Check `acceptTermsAndAgreements` checkbox.
   - **Step 6: Review, Submission & Verification**:
     - Click `Submit` (`[data-automation-id="pageFooterNextButton"]`).
     - Verify explicit employer modal: `Application Submitted - Thank you for applying! You have no more tasks.` and status `In Progress` at `/jobTasks/completed/application`.
     - Log submission to Google Sheet using `log_application.py` with Col D strictly blank.

---

## Central Google Sheets Tracker Protocol

Whenever an application is confirmed submitted:

1. **Direct Service Account Connection**:
   - The central tracker is authenticated using the local Google Cloud service account:
     - Account: `your-service-account@your-project.iam.gserviceaccount.com`
     - Keyfile: `~/.config/gcloud/legacy_credentials/your-service-account@your-project.iam.gserviceaccount.com/adc.json`
     - Spreadsheet: `YOUR_GOOGLE_SHEET_ID`
2. **Execute Logging Script**:
   Run the dedicated script directly:
   ```bash
   python3 ~/.agents/skills/resume-tailor-swe/scripts/log_application.py \
     --company "<Company Name>" \
     --role "<Role Title>" \
     --link "<Job URL>" \
     --notes "<Location. Estimated salary. Submission confirmed. No US sponsorship required.>"
   ```
3. **Strict Column Rules (Row Schema)**:
   - **Col A (`Company Name`)**: Exact employer name.
   - **Col B (`Application Status`)**: `Submitted - Pending Response`.
   - **Col C (`Role`)**: Exact job title.
   - **Col D (`Salary`)**: **MANDATORY: LEAVE BLANK (`""`)**. Never write salary ranges into Col D; all existing rows leave Col D empty.
   - **Col E (`Date Submitted`)**: `M/D/YYYY` format (e.g. `9/7/2026`).
   - **Col F (`Link to Job Req`)**: Job posting link.
   - **Col G (`Rejection Reason`)**: `N/A`.
   - **Col H (`Notes`)**: Location/work mode, salary range, confirmation details, sponsorship notes.
4. **Contiguous Row Enforcement**:
   - Find the first empty row where Col A is blank or an empty template row.
   - Never skip rows and never create duplicate entries.

---

## Autonomous Parallel Application Engine & Multi-Session Handoff

For high-volume autonomous job applications across Greenhouse, Lever, and Ashby, use the battle-tested parallel engine located at `application_engine/`:

### 1. Engine Capabilities & Architecture
- **Orchestrator (`application_engine/parallel_orchestrator.py`)**: Launches 5 parallel Playwright workers concurrently. Partitions target queues disjointly across workers with zero overlap.
- **Unified Runner (`application_engine/batch_apply_multi_ats.py`)**: Supports Greenhouse, Lever, and Ashby natively. Enforces candidate ground truth, fast 25s timeout on dead-ends, and 5s break on visible form errors.
- **Automated Gmail OTP Retrieval (`application_engine/email_verification_helper.py`)**: Automatically retrieves 8-character Greenhouse verification codes (and 6-digit Workday PINs) from `candidate_email@example.com` via ScriptingBridge without stealing focus from the user's active Chrome browser.
- **Shared File Locks**:
  - `/tmp/gspread_sheet_lock.lock`: Synchronizes Google Sheet appends across parallel workers.
  - `/tmp/email_otp_lock.lock`: Prevents multiple workers from querying Gmail simultaneously.
- **Local Sheet Caching**: Caches sheet rows in `/tmp/applied_sheet_records.json` (300s TTL) to eliminate Google Sheets API rate-limit errors during worker startup.

### 2. Candidate Ground Truth Quick Reference
- **Standardized Tests**: SAT: `1280` (handles ranges e.g. `1201 - 1300`; never select `<1200`). ACT: `Did not take` / `I don't have ACT score`. GRE: `Did not take` / `Not applicable`. High School: `Before 2021` / `2020`.
- **Education**: State University; BS CS May 2024 (Summa Cum Laude, GPA 3.86); MS CS projected May 2028 (`Spring 2028` / `Jan - April 2028` / `May - Aug 2028` / `2027 & later`).
- **Degree In-Progress**: `Master's Degree` / `Masters`.
- **Institution Filtering**: Strictly answer `No` if asked if currently enrolled at non-enrolled schools (Northeastern, Columbia, Harvard, MIT, Stanford, NYU).
- **Work Auth**: US Citizen, Authorized for any employer (`Yes`), No visa sponsorship required now or in future (`No`).
- **Demographics**: Gender `Male` / `Man`, Pronouns `He / Him`, Race `Asian` / `South Asian` (Bangladeshi), Veteran `Not a protected veteran`, Disability `No, I do not have a disability and have not had one in the past`.
- **Punctuation**: Strictly ZERO dashes (`-`, `–`, `—`) in application free-text boxes.

### 3. Active Target Queues & Operational Handoff
- **Primary Queue**: `application_engine/queue_unapplied_gh_lever_ashby.json` (655 prioritized, company-interleaved targets).
- **Workday Queue**: `application_engine/queue_workday.json` (184 targets; credentials: `candidate_email@example.com` | `YourWorkdayPassword123!#`).
- **Full Operational Handoff Guide**: See [engine_handoff_guide.md](references/engine_handoff_guide.md).

### 4. Resume Commands for Any Future Agent / Chat
```bash
# 1. Clean check
ps aux | grep -E "parallel_orchestrator|batch_apply_multi_ats" | grep -v grep || echo "Clean"

# 2. Launch 5-worker parallel batch on 655 targets
python3 -u application_engine/parallel_orchestrator.py 655 application_engine/queue_unapplied_gh_lever_ashby.json

# 3. Monitor live progress across workers
for i in {0..4}; do echo "=== WORKER $i ==="; tail -n 5 scratch/parallel_logs/worker_$i.log; done
```

### 5. Daily Fresh Role Discovery Protocol
Whenever instructed to find internships or jobs:
- **Always harvest fresh, newly-opened postings every day** rather than recycling old queues.
- Run `python3 application_engine/fetch_fresh_internships.py` to scour live repositories (SimplifyJobs Summer 2027/2026, New Grad, Pitt CSC) and ATS career endpoints.
- Strictly filter out all confirmed submissions in Google Sheet (`YOUR_GOOGLE_SHEET_ID`) by both exact URL and normalized `(company, title)`.
- Enforce Computer Science / SWE discipline and round-robin company interleaving before launching the parallel orchestrator.
