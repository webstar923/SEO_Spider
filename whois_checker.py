import json
import requests
import os

class WhoisChecker:
    def __init__(self, api_key=None):
        self.api_key = api_key
        if not self.api_key:
            self.api_key = self._load_api_key_from_settings()
        print(self.api_key)
    
    def _load_api_key_from_settings(self):
        settings_file = "settings.json"
        try:
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    return settings.get("api_key", "")
            return ""
        except Exception:
            return ""
    
    def set_api_key(self, key):
        self.api_key = key
        # Save to settings.json
        settings_file = "settings.json"
        settings = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                pass
        
        settings["api_key"] = key
        
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f)

    def check_domain(self, domain):
        url = f'https://api.api-ninjas.com/v1/whois?domain={domain}'
        headers = {'X-Api-Key': self.api_key}
        try:
            response = requests.get(url, headers=headers, timeout=100)
            if response.status_code == 200:
                data = response.json()
                
                # Extract owner information
                owner = data.get("name", "")
                if not owner:
                    owner = data.get("org", "")
                
                # Extract registrar information
                registrar = data.get("registrar", "Unknown")
                
                # Create a dictionary with owner and status information
                return {
                    "owner": owner,
                    "status": registrar
                }
            else:
                error_msg = response.json().get('error', 'Unknown error')
                return {
                    "owner": "Error",
                    "status": f"WHOIS error: {error_msg}"
                }
        except Exception as e:
            return {
                "owner": "Error",
                "status": f"WHOIS exception: {str(e)}"
            }