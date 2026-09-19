# Connecting Google Sheets, Google Drive & Services to AIJobAssistant

This guide explains how to connect your **Google Sheets**, **Google Drive**, and **Email** to AIJobAssistant, as well as how the engine tracks applications locally with zero configuration.

---

## 📊 Application Tracking Options

You have two choices for tracking submitted job applications:

| Feature | Local Markdown Tracker (Default) | Google Sheets Tracker (Cloud Sync) |
| :--- | :--- | :--- |
| **Setup Needed** | **Zero Setup** (100% automatic) | ~3 minutes (Google Cloud Service Account) |
| **Storage Location** | `references/application_tracking.md` | Your personal Google Spreadsheet |
| **Internet / API Keys** | None required (works 100% offline) | Google Cloud API credentials |
| **Multi-Device Sync** | Tracked via local git/workspace | Real-time live cloud sync |

---

## 🚀 Setting Up Google Sheets & Drive Cloud Tracking

If you want your applications to be automatically logged to a Google Sheet, follow these simple steps:

### Step 1: Create a Google Cloud Project & Enable APIs
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one), e.g., `Job-Application-Assistant`.
3. In the search bar at the top, search for and **Enable** both:
   * **Google Sheets API**
   * **Google Drive API**

### Step 2: Create a Service Account & Download JSON Key
1. In the left navigation, go to **APIs & Services > Credentials**.
2. Click **Create Credentials** at the top and select **Service Account**.
3. Name your service account (e.g. `sheets-logger`) and click **Create and Continue**, then click **Done**.
4. Click on the newly created service account in the list to open its details.
5. Go to the **Keys** tab > **Add Key** > **Create new key**.
6. Select **JSON** and click **Create**.
7. A `.json` key file will download to your computer. Save it in a safe location, for example:
   * `~/.config/gcloud/service_account.json`, or
   * Inside your project folder (e.g. `./credentials.json`, note that this file is automatically gitignored).

### Step 3: Create Your Google Sheet & Share It
1. Open [Google Sheets](https://sheets.new) and create a new spreadsheet.
2. In the header row (Row 1), set up the following 8 columns:
   | Col A | Col B | Col C | Col D | Col E | Col F | Col G | Col H |
   | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
   | **Company** | **Status** | **Role** | **Salary** | **Date Applied** | **Job Link** | **Rejection Reason** | **Notes** |

3. Copy the **Service Account Email** (looks like `sheets-logger@your-project.iam.gserviceaccount.com`).
4. In your Google Sheet, click the green **Share** button in the top right corner.
5. Paste the Service Account email address, ensure its role is set to **Editor**, uncheck "Notify people", and click **Share**.
6. Copy your **Spreadsheet ID** from the browser URL:
   ```text
   https://docs.google.com/spreadsheets/d/1ne7TIUj4dIInY8TSrIViwUz9lQplyzJCsGWWgrJZEUY/edit
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                      This is your Sheet ID
   ```

### Step 4: Add Your Sheet ID & Key to AIJobAssistant
You can configure Google Sheets in either of two ways:

#### Option A: During Initial Setup
Run the setup wizard with your sheet details:
```bash
python init_setup.py --sheet-id YOUR_SPREADSHEET_ID --sheet-key /path/to/service_account.json
```
*(Or answer `y` when prompted by `python init_setup.py --interactive`)*

#### Option B: In `config.json`
Add or update the following keys in your local `config.json`:
```json
{
  "google_sheet_id": "YOUR_SPREADSHEET_ID_HERE",
  "google_service_account_key": "/path/to/service_account.json"
}
```

That's it! Every confirmed application submitted by the engine or your AI agent will automatically be appended as a new row to your Google Sheet.

---

## 🔒 Privacy & Safety Guarantee
* Your Service Account JSON key and Google Sheet ID are stored strictly in `config.json` and local paths.
* `config.json`, `*.json` key files, and personal credentials are listed in `.gitignore` and will **never** be committed or uploaded to GitHub.

---

## 📥 Zero-Config Fallback: Local Markdown Tracker
If you do not set up Google Sheets, **no action is required**. The application engine automatically logs every confirmed application to:
```text
references/application_tracking.md
```
This file includes an easy-to-read table with the submission date, company, role title, job URL, resume used, and status. It is 100% private, offline, and ready from day one.

---

## 📬 Connecting Email for Verification Codes (OTP)

When ATS platforms like Greenhouse or Workday send an email verification PIN or security code:
* **macOS + Google Chrome (Automatic)**: Keep Google Chrome open with Gmail logged in on any tab. The engine automatically and silently detects incoming verification codes via macOS ScriptingBridge without stealing your window focus.
* **Manual or Notification Fallback**: If Chrome is closed or on other operating systems, the engine or agent will prompt you in chat to provide the code, and will immediately autofill and resume the application.
