#!/usr/bin/env python
"""
Script to run the FastAPI app with ngrok tunnel for local testing
"""
import subprocess
import sys
from pyngrok import ngrok
import time

# Set ngrok auth token (optional but recommended)
# ngrok.set_auth_token("your_ngrok_token")

# Kill any existing ngrok tunnels
ngrok.kill()

# Create ngrok tunnel to localhost:8001
print("🔗 Creating ngrok tunnel to localhost:8001...")
public_url = ngrok.connect(8001, bind_tls=True)
print(f"\n✅ Tunnel created!")
print(f"📱 Public URL: {public_url}")
print(f"\n🔗 Use this URL for Meta Webhook: {public_url}/webhooks/whatsapp")
print(f"🔑 Token: vibecoding")
print("\n" + "="*60)
print("The FastAPI server should already be running on localhost:8001")
print("Keep this terminal open to maintain the tunnel")
print("="*60 + "\n")

try:
    # Keep the tunnel alive
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n🛑 Closing tunnel...")
    ngrok.kill()
    print("Tunnel closed")
