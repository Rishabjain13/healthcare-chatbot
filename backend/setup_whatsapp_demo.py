#!/usr/bin/env python3
"""
Simple Setup Script for WhatsApp Demo
This will guide you through setting up WhatsApp Sandbox step-by-step
"""

import os
import sys
import time

class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print("\n" + "=" * 70)
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print("=" * 70 + "\n")

def print_step(number, title):
    print(f"\n{Colors.BOLD}{Colors.GREEN}Step {number}: {title}{Colors.END}\n")

def print_info(text):
    print(f"{Colors.YELLOW}💡 {text}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def wait_for_enter(message="Press Enter to continue..."):
    input(f"\n{Colors.CYAN}{message}{Colors.END}")

def main():
    print_header("🎯 WhatsApp Demo Setup - Super Simple Guide")

    print(f"{Colors.BOLD}This script will help you set up WhatsApp Sandbox for your team demo!{Colors.END}")
    print("\nWhat you'll need:")
    print("  • Twilio Account (free)")
    print("  • Your phone with WhatsApp")
    print("  • 10 minutes of time\n")

    wait_for_enter("Ready? Press Enter to start...")

    # Step 1: Get Twilio Credentials
    print_step(1, "Get Your Twilio Credentials")
    print("1. Open this link in your browser:")
    print(f"   {Colors.CYAN}https://console.twilio.com/{Colors.END}\n")
    print("2. You'll see your dashboard with:")
    print("   • Account SID (starts with 'AC...')")
    print("   • Auth Token (click eye icon to reveal)")
    print("\n3. Copy both values - you'll paste them next!\n")

    wait_for_enter()

    print("\n" + Colors.BOLD + "Enter your Twilio credentials:" + Colors.END)
    account_sid = input(f"{Colors.YELLOW}Account SID:{Colors.END} ").strip()
    auth_token = input(f"{Colors.YELLOW}Auth Token:{Colors.END} ").strip()

    if not account_sid or not auth_token:
        print_error("Credentials cannot be empty!")
        sys.exit(1)

    print_success("Credentials saved!")

    # Step 2: OpenAI API Key
    print_step(2, "OpenAI API Key (Optional for now)")
    print("For the demo, you can use OpenAI for complex questions.")
    print(f"{Colors.YELLOW}If you don't have it now, press Enter to skip{Colors.END}\n")

    openai_key = input(f"{Colors.YELLOW}OpenAI API Key (or press Enter):{Colors.END} ").strip()

    if not openai_key:
        openai_key = "your_openai_key_here"
        print_info("Skipped - Bot will use RASA only")
    else:
        print_success("OpenAI key saved!")

    # Update .env file
    print_step(3, "Updating Configuration")

    env_content = f"""# Server
PORT=3000

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID={account_sid}
TWILIO_AUTH_TOKEN={auth_token}
TWILIO_WHATSAPP_NUMBER=+14155238886

# RASA
RASA_URL=http://localhost:5005

# OpenAI
OPENAI_API_KEY={openai_key}

# Confidence threshold
CONFIDENCE_THRESHOLD=0.70
"""

    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print_success("Configuration file updated!")
    except Exception as e:
        print_error(f"Error updating .env: {str(e)}")
        sys.exit(1)

    # Step 4: WhatsApp Sandbox Setup
    print_step(4, "Join WhatsApp Sandbox")

    print(f"{Colors.BOLD}Now grab your phone!{Colors.END}\n")
    print("1. Open WhatsApp on your phone")
    print(f"2. Add this number to contacts: {Colors.GREEN}+1 415 523 8886{Colors.END}")
    print("3. Send a message to that number\n")

    print(f"{Colors.YELLOW}To get your join code:{Colors.END}")
    print(f"   Open: {Colors.CYAN}https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn{Colors.END}")
    print(f"   You'll see: {Colors.GREEN}'join your-code-here'{Colors.END}\n")

    sandbox_code = input(f"{Colors.YELLOW}What's your sandbox code? (e.g., 'yellow-tiger'):{Colors.END} ").strip()

    print(f"\n{Colors.BOLD}Great! Now on WhatsApp:{Colors.END}")
    print(f"   Send this message: {Colors.GREEN}join {sandbox_code}{Colors.END}")
    print(f"   To: {Colors.GREEN}+1 415 523 8886{Colors.END}\n")

    print("You should receive a confirmation message!")

    wait_for_enter("Got the confirmation? Press Enter...")

    print_success("WhatsApp Sandbox activated!")

    # Step 5: Make Server Accessible
    print_step(5, "Make Your Server Accessible (Using ngrok)")

    print("Twilio needs to reach your server. We'll use ngrok!\n")

    # Check if ngrok is installed
    ngrok_installed = os.system("which ngrok > /dev/null 2>&1") == 0

    if not ngrok_installed:
        print_info("ngrok is not installed. Installing now...")
        print("Running: brew install ngrok")
        os.system("brew install ngrok")
    else:
        print_success("ngrok is already installed!")

    print(f"\n{Colors.BOLD}In a NEW terminal window, run:{Colors.END}")
    print(f"   {Colors.GREEN}ngrok http 3000{Colors.END}\n")
    print("You'll see a URL like:")
    print(f"   {Colors.CYAN}https://abc123.ngrok.io{Colors.END}\n")

    wait_for_enter("Started ngrok? Press Enter...")

    ngrok_url = input(f"\n{Colors.YELLOW}Paste your ngrok HTTPS URL:{Colors.END} ").strip()

    if not ngrok_url.startswith('https://'):
        print_error("URL must start with https://")
        sys.exit(1)

    webhook_url = f"{ngrok_url}/whatsapp/webhook"

    print(f"\n{Colors.BOLD}Now configure Twilio webhook:{Colors.END}\n")
    print(f"1. Open: {Colors.CYAN}https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox{Colors.END}")
    print(f"2. Find 'WHEN A MESSAGE COMES IN'")
    print(f"3. Paste this URL: {Colors.GREEN}{webhook_url}{Colors.END}")
    print(f"4. Make sure method is: {Colors.GREEN}POST{Colors.END}")
    print(f"5. Click {Colors.GREEN}Save{Colors.END}\n")

    wait_for_enter("Webhook configured? Press Enter...")

    # Final step
    print_header("🎉 Setup Complete! Ready for Demo!")

    print(f"{Colors.BOLD}Now start your servers:{Colors.END}\n")

    print(f"{Colors.YELLOW}Terminal 1 - RASA (if not running):{Colors.END}")
    print(f"   cd ~/Desktop/healthcare-chatbot/rasa-bot")
    print(f"   rasa run --enable-api --cors \"*\" --port 5005\n")

    print(f"{Colors.YELLOW}Terminal 2 - Backend:{Colors.END}")
    print(f"   cd ~/Desktop/healthcare-chatbot/backend")
    print(f"   python3 server.py\n")

    print(f"{Colors.YELLOW}Terminal 3 - ngrok (already running!):{Colors.END}")
    print(f"   ngrok http 3000\n")

    print(f"{Colors.BOLD}{Colors.GREEN}Test Your Bot:{Colors.END}")
    print(f"1. Open WhatsApp")
    print(f"2. Message: {Colors.GREEN}+1 415 523 8886{Colors.END}")
    print(f"3. Try: 'hello', 'what are your hours', 'كم السعر'\n")

    print(f"{Colors.BOLD}{Colors.CYAN}To Show Your Team:{Colors.END}")
    print(f"1. Ask team to save: {Colors.GREEN}+1 415 523 8886{Colors.END}")
    print(f"2. Send them the join code: {Colors.GREEN}join {sandbox_code}{Colors.END}")
    print(f"3. They can start chatting with the bot!\n")

    print("=" * 70)
    print(f"{Colors.GREEN}✅ You're all set! Good luck with your demo! 🚀{Colors.END}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Setup cancelled.{Colors.END}\n")
        sys.exit(0)
