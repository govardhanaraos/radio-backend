import sys
import os
sys.path.append(r"d:\PythonProjects\GRRadio\backend")
from hindiflacs.hindiflacs_album_details_parsing import parse_album_details
import json
import unittest
from unittest.mock import patch

class Resp:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        pass

def mock_get(*args, **kwargs):
    with open('14-Phere-2021-A1ufbb.html', 'r', encoding='utf-8') as f:
        return Resp(f.read())

if __name__ == "__main__":
    link = "14-Phere-2021-A1ufbb.html"
    try:
        with patch('requests.get', side_effect=mock_get):
            details = parse_album_details(link)
            print("Success! Details:")
            print(json.dumps(details, indent=2, default=str))
    except Exception as e:
        print(f"Error: {e}")
