import requests
import json

# Test the create API directly
url = "http://localhost:8000/api/mymemo/create"
payload = {
    "content": "",
    "title": "TEST",
    "meta_data": {
        "smemo_type": "note",
        "relX": 0.4,
        "relY": 0.4,
        "rotation": 0,
        "color": "#d4d46a"
    }
}

headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {response.headers}")
    print(f"Response Text: {response.text[:500]}")
    
    if response.status_code == 200:
        print(f"JSON Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
