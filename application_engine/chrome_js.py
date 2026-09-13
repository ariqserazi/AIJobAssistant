import subprocess
import json
import sys

def run_js(js_code: str) -> str:
    escaped = js_code.replace('\\', '\\\\').replace('"', '\\"')
    apple_script = f'tell application "Google Chrome" to execute front window\'s active tab javascript "{escaped}"'
    res = subprocess.run(["osascript", "-e", apple_script], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"AppleScript error: {res.stderr}")
    return res.stdout.strip()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        code = sys.argv[1]
    else:
        code = sys.stdin.read()
    print(run_js(code))
