import requests
import json

url = "https://support.hp.com/wcc-services/profile/devices/warranty/specs?cache=true&authState=anonymous&template=ProductModel"
headers = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "User-Agent": "insomnia/11.1.0"
}
body = {
    "cc": "br",
    "lc": "pt",
    "utcOffset": "M0300",
    "customerId": "",
    "deviceId": 1234,
    "devices": [
        {
            "seriesOid": None,
            "modelOid": None,
            "serialNumber": None,
            "productNumber": "A08KLUT"
        }
    ],
    "captchaToken": ""
}

resp = requests.post(url, headers=headers, json=body, timeout=10)
print("Status:", resp.status_code)
print("Body:", resp.text)