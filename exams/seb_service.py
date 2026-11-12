# exams/seb_service.py
"""
Safe Exam Browser 3.x integration service.
Generates .seb config files and verifies ConfigKeyHash headers.
Official spec: https://safeexambrowser.org/developer/seb-config-key.html
"""

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
    """Return compact JSON string with sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def generate_config_key(config_dict):
    """
    Compute SEB Config Key from a config dict.
    Per spec: remove originatorVersion, order keys, compact JSON, SHA256.
    """
    clean = {k: v for k, v in config_dict.items() if k != 'originatorVersion'}
    json_str = _ordered_json(clean)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def verify_config_key_hash(absolute_url, config_key_hash, received_hash):
    """
    Verify X-SafeExamBrowser-ConfigKeyHash header.
    Formula: SHA256(absoluteURL + config_key_hash) == received_hash
    """
    if not received_hash or not config_key_hash:
        return False
    expected = hashlib.sha256(
        (absolute_url + config_key_hash).encode('utf-8')
    ).hexdigest()
    return secrets.compare_digest(expected, received_hash)


def build_seb_config(exam):
    """
    Build the SEB 3.x config dict for this exam.
    startURL points to backend entry endpoint (SEB verifies here, then redirects).
    """
    base = settings.SEB_BASE_URL.rstrip('/')
    frontend = settings.FRONTEND_URL.rstrip('/')
    
    # ✅ Use backend entry URL so SEB verification works
    entry_url = f"{base}/api/exams/{exam.id}/seb-entry/"

    config = {
        "startURL": entry_url,  # ✅ Reverted to backend entry point
        "sendBrowserExamKey": True,
        "allowQuit": True,
        "allowSwitchToApplications": False,
        "allowFlashFullscreen": False,
        "browserViewMode": 1,  # fullscreen
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
            # ✅ Fixed capitalization (Active, Expression, Action)
            {"Active": True, "Expression": base, "Action": 1},
            {"Active": True, "Expression": frontend, "Action": 1},
            {"Active": True, "Expression": "*", "Action": 0},
        ],
        "examSessionClearCookiesOnStart": True,
        "examSessionClearCookiesOnEnd": True,
        "quitURL": f"{base}/api/exams/{exam.id}/seb-quit/",
    }
    return config


def generate_seb_file(exam):
    """
    Generate .seb file as unencrypted XML plist (SEB 3.x compatible).
    """
    config = build_seb_config(exam)
    config_key = generate_config_key(config)

    # SEB requires plist XML format
    buffer = BytesIO()
    plistlib.dump(config, buffer, fmt=plistlib.FMT_XML)
    file_bytes = buffer.getvalue()

    return config_key, file_bytes


def generate_and_save(exam):
    """
    Generate SEB file and attach to exam. Called automatically on publish.
    """
    if not getattr(settings, 'SEB_ENABLED', False):
        return None

    config_key, file_bytes = generate_seb_file(exam)

    filename = f"exam_{exam.id}_seb.seb"
    exam.seb_config_file.save(filename, ContentFile(file_bytes), save=False)
    exam.seb_config_key = config_key
    exam.seb_generated_at = timezone.now()
    exam.seb_enabled = True
    exam.save(update_fields=[
        'seb_config_file', 'seb_config_key', 'seb_generated_at', 'seb_enabled'
    ])
    return config_key