"""
This script runs all 10 test scenarios as real phone calls.
It starts the server, sets up a tunnel, and calls the test number.
"""

import os
import sys
import re
import time
import json
import subprocess
import threading
import urllib.request
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Twilio stuff - copied from the old call_manager.py
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import requests

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")
DESTINATION_PHONE = "+18054398008"  # the test number from the doc
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")

twilio_client = Client(TWILIO_SID, TWILIO_AUTH)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(PROJECT_DIR, ".env")
LOG_FILE = "/tmp/server.log"
TUNNEL_LOG = "/tmp/tunnel.log"


# ---- Twilio call functions (these used to be in call_manager.py) ----

def make_call(scenario_id):
    """Make an outbound call using Twilio. Returns the call SID."""
    try:
        url = f"{SERVER_URL}/handle-call?scenario_id={scenario_id}"
        call = twilio_client.calls.create(
            to=DESTINATION_PHONE,
            from_=TWILIO_PHONE,
            url=url,
            status_callback=f"{SERVER_URL}/call-status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST",
            record=True,
            timeout=300
        )
        print(f"[Call] Started call {call.sid} for scenario {scenario_id}")
        return call.sid
    except TwilioRestException as e:
        print(f"[Call Error] {e}")
        return None


def get_call_status(call_sid):
    """Get the current status of a call."""
    try:
        call = twilio_client.calls(call_sid).fetch()
        return {
            "sid": call.sid,
            "status": call.status,
            "duration": call.duration,
        }
    except TwilioRestException as e:
        print(f"[Call Error] {e}")
        return {"status": "error"}


def end_call(call_sid):
    """End an active call."""
    try:
        twilio_client.calls(call_sid).update(status="completed")
        print(f"[Call] Ended call {call_sid}")
    except TwilioRestException as e:
        print(f"[Call Error] {e}")


def download_recording(call_sid, save_dir="recordings"):
    """Download the call recording from Twilio. Tries a few times in case it's not ready yet."""
    os.makedirs(save_dir, exist_ok=True)

    for attempt in range(5):
        try:
            recordings = twilio_client.recordings.list(call_sid=call_sid)
            if not recordings:
                if attempt < 4:
                    time.sleep(5)
                    continue
                print(f"[Recording] No recording found for {call_sid}")
                return None

            recording = recordings[0]
            wav_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Recordings/{recording.sid}.wav"

            response = requests.get(wav_url, auth=(TWILIO_SID, TWILIO_AUTH))
            if response.status_code == 200 and len(response.content) > 100:
                wav_path = os.path.join(save_dir, f"{call_sid}.wav")
                with open(wav_path, "wb") as f:
                    f.write(response.content)
                print(f"[Recording] Downloaded WAV: {wav_path}")

                # convert to ogg using ffmpeg
                ogg_path = os.path.join(save_dir, f"{call_sid}.ogg")
                ffmpeg = os.path.expanduser("~/.local/bin/ffmpeg")
                try:
                    subprocess.run(
                        [ffmpeg, "-y", "-i", wav_path, "-c:a", "libopus", "-b:a", "32k", ogg_path],
                        capture_output=True, check=True
                    )
                    os.remove(wav_path)
                    print(f"[Recording] Converted to OGG: {ogg_path}")
                    return ogg_path
                except (subprocess.CalledProcessError, FileNotFoundError):
                    print(f"[Recording] ffmpeg conversion failed, keeping WAV")
                    return wav_path
            elif response.status_code == 404 or len(response.content) <= 100:
                if attempt < 4:
                    time.sleep(5)
                    continue
                print(f"[Recording] Not ready after retries")
                return None
            else:
                print(f"[Recording] Failed: {response.status_code}")
                return None

        except TwilioRestException as e:
            print(f"[Recording Error] {e}")
            return None

    return None


# ---- Tunnel functions (these used to be in launch.py) ----

def update_env_tunnel_url(url):
    """Update the SERVER_URL in .env file with the tunnel URL."""
    with open(ENV_FILE, "r") as f:
        content = f.read()
    content = re.sub(r"SERVER_URL=.*", f"SERVER_URL={url}", content)
    with open(ENV_FILE, "w") as f:
        f.write(content)
    print(f"[Tunnel] Updated .env with: {url}")


def wait_for_tunnel_url(timeout=60):
    """Wait for cloudflared to give us a URL."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with open(TUNNEL_LOG, "r") as f:
                for line in f:
                    match = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
                    if match:
                        return match.group(1)
        except FileNotFoundError:
            pass
        time.sleep(1)
    return None


def start_tunnel():
    """Start cloudflared tunnel and update .env with the URL."""
    print("[Tunnel] Starting cloudflared...")
    tunnel_proc = subprocess.Popen(
        [os.path.expanduser("~/.local/bin/cloudflared"), "tunnel", "--url", "http://localhost:8000"],
        stdout=open(TUNNEL_LOG, "w"),
        stderr=subprocess.STDOUT
    )

    print("[Tunnel] Waiting for URL...")
    tunnel_url = wait_for_tunnel_url(timeout=60)
    if not tunnel_url:
        print("[Tunnel] ERROR: Could not get tunnel URL")
        tunnel_proc.kill()
        return None

    update_env_tunnel_url(tunnel_url)
    return tunnel_proc


def start_server():
    """Start the FastAPI server in the background."""
    # clear old log
    open(LOG_FILE, "w").close()

    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=open(LOG_FILE, "w"),
        stderr=subprocess.STDOUT,
        cwd=PROJECT_DIR
    )
    time.sleep(4)

    # check if it's actually up
    for i in range(5):
        try:
            urllib.request.urlopen("http://localhost:8000/", timeout=5)
            print("[Server] Server is up")
            return proc
        except Exception:
            if i < 4:
                time.sleep(2)
            else:
                print("[Server] ERROR: Server failed to start")
                proc.kill()
                return None

    return proc


def kill_old_processes():
    """Kill any leftover processes from previous runs."""
    subprocess.run(["pkill", "-9", "-f", "uvicorn"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "main:app"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "cloudflared"], capture_output=True)
    time.sleep(2)


# ---- Main test runner ----

def run_all_scenarios():
    """Run all 10 test scenarios as phone calls."""

    from scenarios import list_scenarios

    # kill old stuff first
    kill_old_processes()

    # start tunnel
    tunnel_proc = start_tunnel()
    if not tunnel_proc:
        return

    # start server
    server_proc = start_server()
    if not server_proc:
        tunnel_proc.kill()
        return

    # tail thread for live transcript
    stop_event = threading.Event()

    def tail_log():
        while not stop_event.is_set():
            try:
                with open(LOG_FILE, "r") as f:
                    f.seek(0, 2)
                    while not stop_event.is_set():
                        line = f.readline()
                        if line:
                            line = line.strip()
                            if "[AI]" in line or "[User]" in line:
                                print(f"  {line}")
                        else:
                            time.sleep(0.3)
            except Exception:
                time.sleep(0.5)

    tail_thread = threading.Thread(target=tail_log, daemon=True)
    tail_thread.start()

    # print banner
    print("\n" + "=" * 60)
    print("PRETTY GOOD AI - VOICE BOT TEST RUNNER")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target:  +18054398008")
    print(f"Scenarios: 10")
    print("=" * 60)

    # import here after load_dotenv
    from scenarios import list_scenarios

    results = []
    scenario_names = list_scenarios()

    for i, scenario_name in enumerate(scenario_names, 1):
        print(f"\n{'=' * 60}")
        print(f"SCENARIO {i}: {scenario_name.upper().replace('_', ' ')}")
        print(f"{'=' * 60}")

        # make the call
        call_sid = make_call(i)
        if not call_sid:
            print(f"  FAILED to initiate call")
            results.append({"scenario": scenario_name, "scenario_id": i, "status": "failed"})
            continue

        print(f"  Call SID: {call_sid}")

        # wait for call to finish
        start_time = time.time()
        max_duration = 5 * 60  # 5 min timeout

        while True:
            status = get_call_status(call_sid)
            current = status.get("status", "unknown")
            if current in ["completed", "failed", "busy", "no-answer", "canceled"]:
                break
            if time.time() - start_time > max_duration:
                print(f"\n  TIMEOUT, ending call...")
                end_call(call_sid)
                break
            time.sleep(3)

        # get final status and recording
        final = get_call_status(call_sid)
        duration = final.get("duration", "0")
        recording = download_recording(call_sid, "recordings")

        icon = "OK" if final.get("status") == "completed" else "FAIL"
        print(f"\n  [{icon}] {scenario_name} - {final.get('status')} ({duration}s)")

        results.append({
            "scenario": scenario_name,
            "scenario_id": i,
            "call_sid": call_sid,
            "status": final.get("status"),
            "duration": duration,
            "recording_file": recording
        })

        # wait between calls
        if i < len(scenario_names):
            print(f"\n  Waiting 10s before next call...")
            time.sleep(10)

    # stop tailing
    stop_event.set()

    # print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        icon = "OK" if r.get("status") == "completed" else "FAIL"
        print(f"  [{icon}] {r['scenario_id']:2d}. {r['scenario'].replace('_', ' ').title()}")

    ok = sum(1 for r in results if r.get("status") == "completed")
    print(f"\n  {ok}/{len(results)} completed")
    print("=" * 60)

    # save results to file
    os.makedirs("results", exist_ok=True)
    with open(f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
        json.dump(results, f, indent=2)

    # cleanup
    print("\nShutting down...")
    server_proc.terminate()
    tunnel_proc.terminate()
    print("Done!")


if __name__ == "__main__":
    run_all_scenarios()
