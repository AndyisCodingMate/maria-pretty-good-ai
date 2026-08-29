"""
Run a CUSTOM selection of scenarios as real phone calls.

Just like run_all.py, but instead of always calling all 10 scenarios,
you get to pick which ones you want to test.

Usage:
    python3 run_scenarios.py              # shows a menu where you pick
    python3 run_scenarios.py 1 3 5        # runs scenarios 1, 3 and 5
    python3 run_scenarios.py 2-4          # runs a range: 2, 3, 4
    python3 run_scenarios.py all          # runs all 10 (same as run_all.py)
    python3 run_scenarios.py custom       # write your OWN scenario, then call
    python3 run_scenarios.py custom 7     # your custom scenario + scenario 7
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# reuse the tunnel / server / call helpers from run_all.py so we
# don't have to rewrite them
from run_all import (
    start_tunnel,
    start_server,
    kill_old_processes,
    make_call,
    get_call_status,
    end_call,
    download_recording,
    LOG_FILE,
)

from scenarios import list_scenarios, get_universal_rules, save_custom_scenario


def build_custom_scenario():
    """
    Let the user write their own scenario: an opening line plus the
    instructions Maria should follow. Saves it for the server to use,
    then the call runs just like any normal scenario.
    """
    from scenarios import get_custom_scenario

    print("\n" + "-" * 60)
    print("BUILD A CUSTOM SCENARIO")
    print("-" * 60)
    print("You give Maria a goal and instructions. She then calls the clinic")
    print("and autopilots that scenario to test the other side.\n")

    # opening line - what Maria says first after the other side greets her
    while True:
        opening = input("Maria's opening line: ").strip()
        if opening:
            break
        print("  ...please type an opening line.")

    # optional name
    name = input("Scenario name (Enter for 'Custom Scenario'): ").strip()
    if not name:
        name = "Custom Scenario"

    # the instructions - read until the user types DONE on its own line
    print("\nType Maria's instructions below (who she is, her goal, what to")
    print("ask, the outcome you want). Type DONE on its own line when finished:\n")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "DONE":
            break
        lines.append(line)

    prompt = "\n".join(lines).strip()
    if not prompt:
        print("  (no instructions given - using a generic patient prompt)")
        prompt = ("You are Maria calling the clinic for help. Have a natural "
                  "conversation and achieve your goal.")

    # always include the shared rules so Maria stays in character
    full_prompt = prompt + "\n\n" + get_universal_rules()
    save_custom_scenario(full_prompt, opening, name)

    existing = get_custom_scenario()
    if not existing:
        print("\nERROR: custom scenario did not save correctly, exiting.")
        return None

    print(f"\nCustom scenario ready: {name}")
    return existing


def get_requested_scenario_ids():
    """
    Figure out which scenarios the user wants to run.
    Returns a list of scenario numbers, where 0 means a custom scenario.
    """
    names = list_scenarios()
    total = len(names)

    # scenario numbers passed on the command line
    if len(sys.argv) > 1:
        ids = []
        for arg in sys.argv[1:]:
            if arg == "all":
                return list(range(1, total + 1))
            # "custom" or "0" means a user-written scenario
            if arg.lower() == "custom" or arg == "0":
                ids.append(0)
                continue
            # support ranges like 2-5
            if "-" in arg:
                try:
                    start, end = arg.split("-")
                    start, end = int(start), int(end)
                    ids.extend(range(start, end + 1))
                    continue
                except ValueError:
                    pass
            try:
                ids.append(int(arg))
            except ValueError:
                print(f"  ignoring unknown argument: {arg}")
        # throw away any numbers that aren't valid scenarios
        return sorted(set(i for i in ids if 1 <= i <= total or i == 0))

    # otherwise show an interactive menu
    print()
    print("Which scenarios do you want to run as phone calls?")
    print()
    for i, name in enumerate(names, 1):
        print(f"  {i:2d}. {name.replace('_', ' ').title()}")
    print(f"   0. CUSTOM - write your own scenario")
    print()
    print("  Enter numbers separated by spaces, a range like 1-4,")
    print("  or 'all' to run everything.")
    print()

    while True:
        response = input("> ").strip()
        if not response:
            continue
        if response.lower() == "all":
            return list(range(1, total + 1))

        ids = []
        for part in response.replace(",", " ").split():
            if part.lower() == "custom" or part == "0":
                ids.append(0)
                continue
            if "-" in part:
                try:
                    start, end = part.split("-")
                    ids.extend(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            else:
                try:
                    ids.append(int(part))
                except ValueError:
                    pass

        ids = sorted(set(ids))
        # throw away any numbers that aren't valid scenarios
        ids = [i for i in ids if 1 <= i <= total or i == 0]
        if ids:
            return ids
        print("  Sorry, I didn't understand that. Try again.")


def run_one_scenario(scenario_id, scenario_name):
    """Place one phone call for a scenario and wait for it to finish."""
    print(f"\n{'=' * 60}")
    print(f"SCENARIO {scenario_id}: {scenario_name.upper().replace('_', ' ')}")
    print(f"{'=' * 60}")

    # make the call
    call_sid = make_call(scenario_id)
    if not call_sid:
        print(f"  FAILED to initiate call")
        return {"scenario": scenario_name, "scenario_id": scenario_id, "status": "failed"}

    print(f"  Call SID: {call_sid}")

    # wait for the call to finish (max 5 minutes)
    start_time = time.time()
    max_duration = 5 * 60

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

    # grab the final status and the recording
    final = get_call_status(call_sid)
    duration = final.get("duration", "0")
    recording = download_recording(call_sid, "recordings")

    icon = "OK" if final.get("status") == "completed" else "FAIL"
    print(f"\n  [{icon}] {scenario_name} - {final.get('status')} ({duration}s)")

    return {
        "scenario": scenario_name,
        "scenario_id": scenario_id,
        "call_sid": call_sid,
        "status": final.get("status"),
        "duration": duration,
        "recording_file": recording,
    }


def run():
    """The main function."""
    names = list_scenarios()

    from scenarios import get_custom_scenario

    scenario_ids = get_requested_scenario_ids()
    if not scenario_ids:
        print("No scenarios selected. Exiting.")
        return

    # if the user wants a custom scenario, let them write it now
    if 0 in scenario_ids:
        if build_custom_scenario() is None:
            return

    print(f"\nRunning {len(scenario_ids)} scenario(s): ")
    for sid in scenario_ids:
        if sid == 0:
            custom = get_custom_scenario()
            custom_name = custom["name"] if custom else "Custom Scenario"
            print(f"  - 0. {custom_name}")
        else:
            print(f"  - {sid}. {names[sid - 1].replace('_', ' ').title()}")
    print()

    proceed = input("Press Enter to start the calls (or 'q' to quit): ").strip()
    if proceed.lower() == "q":
        print("Cancelled.")
        return

    # clean up leftover processes, then start tunnel and server
    kill_old_processes()

    tunnel_proc = start_tunnel()
    if not tunnel_proc:
        return

    server_proc = start_server()
    if not server_proc:
        tunnel_proc.kill()
        return

    # tail thread for live transcript output
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

    print("\n" + "=" * 60)
    print("PRETTY GOOD AI - SCENARIO TEST RUNNER")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target:  +18054398008")
    print(f"Scenarios: {', '.join(str(i) for i in scenario_ids)}")
    print("=" * 60)

    # make the calls one at a time
    results = []
    for position, scenario_id in enumerate(scenario_ids):
        if scenario_id == 0:
            custom = get_custom_scenario()
            scenario_name = custom["name"] if custom else "Custom Scenario"
        else:
            scenario_name = names[scenario_id - 1]
        result = run_one_scenario(scenario_id, scenario_name)
        results.append(result)

        # wait between calls
        if position < len(scenario_ids) - 1:
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
    tag = "-".join(str(i) for i in scenario_ids)
    os.makedirs("results", exist_ok=True)
    results_file = f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_scen{tag}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")

    # cleanup
    print("\nShutting down...")
    server_proc.terminate()
    tunnel_proc.terminate()
    print("Done!")


if __name__ == "__main__":
    run()