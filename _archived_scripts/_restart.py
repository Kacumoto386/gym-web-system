"""Restart server - kill all uvicorn, start fresh"""
import subprocess, sys, os, time, json, urllib.request

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PYTHON = r'C:\Users\12225\AppData\Local\Programs\Python\Python312\python.exe'

# Kill all uvicorn processes (use cmd.exe to avoid MSYS2 path mangling)
subprocess.run(['cmd.exe', '/c', 'taskkill /f /im uvicorn.exe'], capture_output=True)
time.sleep(2)

# Start fresh
proc = subprocess.Popen(
    [PYTHON, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', '8080'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
time.sleep(4)

# Verify health
try:
    r = urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=5)
    status = json.loads(r.read())
    print(f'Server OK: {status}')
except Exception as e:
    print(f'Server failed: {e}')
    # Try tasklist to see if still running
    r = subprocess.run(['tasklist', '/fi', 'PID eq %d' % proc.pid], capture_output=True, text=True)
    print(f'Process check: {r.stdout[:200]}')
