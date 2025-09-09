#!/usr/bin/env python3
"""Send alerts via webhook if any exist"""

import json
import os
import requests
from datetime import datetime

def main():
    """Send alerts if they exist"""
    alerts_file = 'data/stop_alerts.json'
    
    if os.path.exists(alerts_file):
        with open(alerts_file, 'r') as f:
            alerts = json.load(f)
        
        if alerts:
            webhook_url = os.environ.get('WEBHOOK_URL')
            if webhook_url:
                message = f"🚨 Stop Loss Alerts ({len(alerts)} positions):\n"
                for alert in alerts:
                    message += f"• {alert['symbol']}: ${alert['current_price']:.2f} (Stop: ${alert['stop_level']:.2f})\n"
                
                try:
                    response = requests.post(webhook_url, json={'content': message})
                    if response.status_code == 200:
                        print("✅ Alerts sent successfully")
                    else:
                        print(f"❌ Failed to send alerts: {response.status_code}")
                except Exception as e:
                    print(f"❌ Error sending alerts: {e}")
            else:
                print("No webhook URL configured")
        else:
            print("No alerts to send")
    else:
        print("No alerts file found")

if __name__ == "__main__":
    main()
