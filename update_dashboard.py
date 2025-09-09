#!/usr/bin/env python3
"""Update dashboard with latest data"""

import json
import os
from datetime import datetime

def main():
    """Update dashboard data"""
    # This script updates dashboard data after main.py runs
    # The main.py script already updates docs/latest.json
    # So this script just confirms the update
    
    if os.path.exists('docs/latest.json'):
        with open('docs/latest.json', 'r') as f:
            data = json.load(f)
        
        print(f"✅ Dashboard updated: Portfolio value ${data.get('portfolio_value', 0):.2f}")
    else:
        print("❌ No dashboard data found")

if __name__ == "__main__":
    main()
