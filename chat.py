"""
Simple text chat interface to test the AI without making phone calls.
This lets you type messages and see what the AI would say.
"""

import os
import sys
from dotenv import load_dotenv
from scenarios import list_scenarios, get_scenario

load_dotenv()

from voice_engine import generate_response, reset_conversation


def print_scenarios():
    """Print out all the available scenarios."""
    print("\nAvailable scenarios:")
    scenarios = list_scenarios()
    for i, name in enumerate(scenarios, 1):
        print(f"  {i}. {name.replace('_', ' ').title()}")
    print()


def text_chat():
    """Run a text-based chat session."""
    print("=" * 50)
    print("PRETTY GOOD AI - TEXT CHAT TESTER")
    print("=" * 50)

    # let user pick a scenario
    print_scenarios()
    try:
        choice = int(input("Pick a scenario (1-10): ")) - 1
        scenarios = list_scenarios()
        if choice < 0 or choice >= len(scenarios):
            choice = 0
    except (ValueError, EOFError):
        choice = 0

    scenario_name = list_scenarios()[choice]
    scenario = get_scenario(scenario_name)
    system_prompt = scenario["prompt"]
    opening = scenario.get("opening", "Hi there!")

    print(f"\nScenario: {scenario_name.replace('_', ' ').title()}")
    print(f"Maria will say: {opening}")
    print("Type your messages below (type 'quit' to exit):\n")

    reset_conversation()

    # have Maria say her opening line
    print(f"[Maria]: {opening}")

    # main chat loop
    while True:
        try:
            user_input = input("[You]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        # get AI response
        response = generate_response(user_input, system_prompt)
        print(f"[Maria]: {response}\n")


def call_menu():
    """Show a menu to make actual phone calls."""
    from run_all import make_call

    print("\n" + "=" * 50)
    print("MAKE A TEST CALL")
    print("=" * 50)
    print_scenarios()

    try:
        choice = int(input("Pick a scenario to call (1-10): "))
        if 1 <= choice <= 10:
            print(f"\nCalling for scenario {choice}...")
            call_sid = make_call(choice)
            if call_sid:
                print(f"Call started! SID: {call_sid}")
            else:
                print("Failed to start call")
        else:
            print("Invalid choice")
    except (ValueError, EOFError):
        print("Invalid input")


if __name__ == "__main__":
    print("\nWhat do you want to do?")
    print("  1. Text chat (no phone call)")
    print("  2. Make a real phone call")

    try:
        choice = input("\nPick (1 or 2): ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if choice == "2":
        call_menu()
    else:
        text_chat()
