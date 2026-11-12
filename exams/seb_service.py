# exams/seb_service.py
import hashlib
import json
import os
import secrets
import plistlib
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import Exam

def _ordered_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def generate_config_key(config_dict):
    clean = {k: v for k, v in config_dict.items() if k != 'originatorVersion'}
    json_str = _ordered_json(clean)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

def verify_config_key_hash(absolute_url, config_key_hash, received_hash):
    if not received_hash or not config_key_hash:
        return False
    expected = hashlib.sha256(
        (absolute_url + config_key_hash).encode('utf-8')
    ).hexdigest()
    return secrets.compare_digest(expected, received_hash)

def build_seb_config(exam):
    base = settings.SEB_BASE_URL.rstrip('/')
    frontend = settings.FRONTEND_URL.rstrip('/')
    
    # ✅ Point to backend entry endpoint
    entry_url = f"{base}/api/exams/{exam.id}/seb-entry/"

    config = {
        "startURL": entry_url,
        "sendBrowserExamKey": True,
        "allowQuit": True,  # Keep true for testing so you can exit!
        "allowSwitchToApplications": False,
        "allowFlashFullscreen": False,
        "browserViewMode": 1,
        "enableJavaScript": True,
        "enablePlugIns": False,
        "showTaskBar": False,
        "showReloadButton": False,
        "showTime": True,
        "showInputLanguage": False,
        "allowBrowsingBackForward": False,
        "browserWindowAllowReload": False,
        "URLFilterEnable": True,
        "URLFilterRules": [
            {"active": True, "expression": "*dems-backend-0dxk.onrender.com*", "action": 1},
            {"active": True, "expression": "*dems-frontend.onrender.com*", "action": 1},
            {"active": True, "expression": "*", "action": 0},
        ],
        "examSessionClearCookiesOnStart": True,
        "examSessionClearCookiesOnEnd": True,
        "quitURL": f"{base}/api/exams/{exam.id}/seb-quit/",
    }
    return config

def generate_seb_file(exam):
    config = build_seb_config(exam)
    config_key = generate_config_key(config)
    buffer = BytesIO()
    plistlib.dump(config, buffer, fmt=plistlib.FMT_XML)
    return config_key, buffer.getvalue()

def generate_and_save(exam):
    if not getattr(settings, 'SEB_ENABLED', False):
        return None
    config_key, file_bytes = generate_seb_file(exam)
    filename = f"exam_{exam.id}_seb.seb"
    exam.seb_config_file.save(filename, ContentFile(file_bytes), save=False)
    exam.seb_config_key = config_key
    exam.seb_generated_at = timezone.now()
    exam.seb_enabled = True
    exam.save(update_fields=['seb_config_file', 'seb_config_key', 'seb_generated_at', 'seb_enabled'])
    return config_key