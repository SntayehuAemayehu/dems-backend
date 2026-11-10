# backend/notifications/sms_service.py
import os
import requests

# Gracefully handle missing textbee package so the server still starts
try:
    from textbee import Textbee
    # SDK client (reads TEXTBEE_API_KEY from environment automatically)
    # TEMPORARY TEST ONLY
    textbee_client = Textbee(api_key="txb_NW7jYMxKZ0TzsR7wiG1r7aYN7snB9OvX")
    _TEXTBEE_AVAILABLE = True
except ImportError:
    textbee_client = None
    _TEXTBEE_AVAILABLE = False
    print("⚠️  WARNING: 'textbee' package not installed. SMS (send_bulk_same_message) will be disabled. Run: pip install textbee")
def format_ethiopian_phone(phone):
    """Format 09... or 9... to +2519..."""
    if not phone:
        return None
    phone = str(phone).strip()
    if phone.startswith('+251'):
        return phone
    if phone.startswith('09'):
        return '+251' + phone[1:]
    if phone.startswith('9'):
        return '+251' + phone
    return phone

def send_bulk_same_message(recipients, message):
    """
    Sends the SAME message to many people.
    Uses the official SDK (POST /gateway/send-sms).
    """
    if not _TEXTBEE_AVAILABLE or textbee_client is None:
        print("❌ send_bulk_same_message: textbee package not available. SMS not sent.")
        return None

    formatted = [format_ethiopian_phone(p) for p in recipients if p]
    formatted = [p for p in formatted if p]

    if not formatted:
        return None

    try:
        result = textbee_client.send_sms(recipients=formatted, message=message)
        if "smsBatchId" in result:
            print(f"✅ Same-message bulk queued: {result['smsBatchId']}")
            return result
    except Exception as e:
        print(f"❌ SDK Error: {e}")
    return None

def send_bulk_personalized(messages_data):
    """
    Sends DIFFERENT messages to different people.
    messages_data format: [{"recipients": ["+2519..."], "message": "Hi Abebe..."}, ...]
    Uses REST API directly (POST /gateway/send-bulk-sms) because the SDK doesn't support this.
    """
    # ✅ FIXED: Use variable names, not the actual keys
    api_key = os.environ.get("TEXTBEE_API_KEY")
    device_id = os.environ.get("TEXTBEE_DEVICE_ID")

    if not api_key:
        print("❌ ERROR: TEXTBEE_API_KEY environment variable is not set.")
        return None

    url = "https://api.textbee.dev/api/v1/gateway/send-bulk-sms"
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Format recipients inside the messages_data
    formatted_messages = []
    for item in messages_data:
        phones = [format_ethiopian_phone(p) for p in item.get("recipients", [])]
        phones = [p for p in phones if p]
        if phones:
            formatted_messages.append({
                "recipients": phones,
                "message": item.get("message", "")
            })

    if not formatted_messages:
        return None

    payload = {
        "messages": formatted_messages
    }
    if device_id:
        payload["deviceId"] = device_id

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        if response.status_code == 200 and data.get("data", {}).get("success"):
            print(f"✅ Personalized bulk queued: {data['data']['smsBatchId']}")
            return data["data"]
        else:
            print(f"❌ Personalized bulk failed: {data}")
    except Exception as e:
        print(f"❌ Request Error: {e}")
    return None