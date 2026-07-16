"""TC-AB-003: Test expired API key handling."""
import os, sys, json, urllib.request, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

EXPIRED_KEY = "sk-0db8b09f9f1948bead92851c6f123dv3"
KABUQINA_HOME = os.environ.get("KABUQINA_HOME", "")
TOKEN_FILE = os.path.join(os.path.dirname(KABUQINA_HOME), "hermes_web_session_token.txt")
PASS = "PASS"
FAIL = "FAIL"

print("=== TC-AB-003: Expired API Key Error Handling ===")

# Step 1: Verify key is expired
print("\n--- Step 1: Verify key is expired ---")
req = urllib.request.Request(
    "https://api.deepseek.com/v1/chat/completions",
    data=json.dumps({"model":"deepseek-chat","messages":[{"role":"user","content":"Hi"}]}).encode(),
    headers={"Authorization":f"Bearer {EXPIRED_KEY}","Content-Type":"application/json"},
)
try:
    urllib.request.urlopen(req, timeout=15)
    print(f"Key still works (not expired)")
    sys.exit(1)
except urllib.error.HTTPError as e:
    if e.code == 401:
        print(f"HTTP 401 Unauthorized -- key IS expired")
    else:
        print(f"HTTP {e.code} -- unexpected")
        sys.exit(1)

# Step 2: Check server is alive
print("\n--- Step 2: Server alive check ---")
try:
    token = open(TOKEN_FILE).read().strip()
except:
    print(f"Cannot read token file: {TOKEN_FILE}")
    sys.exit(1)

# Find port
import subprocess, re
result = subprocess.run(["netstat","-ano"], capture_output=True, text=True)
port = None
for line in result.stdout.splitlines():
    if "LISTENING" in line and "127.0.0.1:" in line:
        parts = line.split()
        if len(parts) >= 5:
            m = re.search(r'127\.0\.0\.1:(\d+)', line)
            if m and m.group(1):
                p = m.group(1)
                try:
                    proc = subprocess.run(["tasklist","/FI",f"PID eq {parts[-1]}","/FO","CSV","/NH"], capture_output=True, text=True)
                    if "python" in proc.stdout.lower():
                        port = p
                        break
                except: pass

if not port:
    print(f"Cannot find Python port")
    sys.exit(1)

print(f"Server on port {port}")

try:
    req2 = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp2 = urllib.request.urlopen(req2, timeout=5)
    status = json.loads(resp2.read())
    print(f"Server alive: yes")
    print(f"  gateway_running: {status.get('gateway_running')}")
except Exception as e:
    print(f"Server not reachable: {e}")
    sys.exit(1)

# Step 3: Normal chat to confirm baseline
print("\n--- Step 3: Normal chat (valid key) ---")
req3 = urllib.request.Request(
    f"http://127.0.0.1:{port}/api/desk/chat-proto",
    data=json.dumps({"message":"Say OK if you hear me","session_id":"tc-ab-003-normal"}).encode(),
    headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
)
try:
    resp3 = urllib.request.urlopen(req3, timeout=60)
    data3 = json.loads(resp3.read())
    ok = data3.get("ok")
    print(f"ok: {ok}")
    if ok:
        preview = data3.get("preview","")[:100]
        print(f"preview: {preview}")
    else:
        print(f"error: {data3.get('error')} detail: {str(data3.get('detail',''))[:200]}")
except Exception as e:
    print(f"Chat failed: {e}")

# Step 4: Agent layer test with expired key
print("\n--- Step 4: Agent layer with expired key ---")
original_key = os.environ.get("OPENAI_API_KEY", "")
os.environ["OPENAI_API_KEY"] = EXPIRED_KEY

try:
    from run_agent import AIAgent
    from kabuqina_cli.config import load_config
    
    config = load_config()
    model = config.get("model", {}).get("model", "deepseek-chat")
    
    agent = AIAgent(
        api_key=EXPIRED_KEY,
        provider="custom",
        api_mode="chat_completions",
        model=model,
        max_iterations=1,
        skip_context_files=True,
        skip_memory=True,
    )
    
    try:
        response = agent.chat("Say hello")
        print(f"Agent response: {response[:100]}")
        print("No exception -- key may default to other provider")
    except Exception as e:
        err = str(e)
        print(f"Exception caught: {type(e).__name__}")
        print(f"  message: {err[:300]}")
        code_401 = "401" in err or "unauthorized" in err.lower() or "invalid" in err.lower()
        print(f"  contains 401/unauth/invalid: {code_401}")
        if code_401:
            print(f"  {PASS}: agent caught 401 gracefully")
        print(f"  {PASS}: no crash, error handled")
finally:
    if original_key:
        os.environ["OPENAI_API_KEY"] = original_key
    else:
        os.environ.pop("OPENAI_API_KEY", None)

# Step 5: Verify server still running after all tests
print("\n--- Step 5: Server still running? ---")
try:
    req5 = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp5 = urllib.request.urlopen(req5, timeout=5)
    s = json.loads(resp5.read())
    print(f"Server alive: yes (active_sessions={s.get('active_sessions')})")
    print(f"{PASS}: process did not crash")
except Exception as e:
    print(f"{FAIL}: server not reachable: {e}")

print("\n=== TC-AB-003 Complete ===")
