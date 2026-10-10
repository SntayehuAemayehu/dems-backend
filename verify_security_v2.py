# verify_security_v2.py
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dems_backend.settings')
django.setup()

from django.test import Client
c = Client()

tests = [
    ("Bot UA",                 "get",  "/api/courses/",  {"HTTP_USER_AGENT": "sqlmap/1.0"}),
    ("Honeypot",               "get",  "/wp-admin",       {}),
    ("Honeypot",               "get",  "/.env",           {}),
    ("NoSQL injection",        "get",  "/api/courses/?x=$where", {}),
    ("SSRF",                   "get",  "/api/courses/?url=http://169.254.169.254/", {}),
    ("XXE",                    "get",  "/api/courses/?x=<!ENTITY foo SYSTEM 'file:///etc/passwd'>", {}),
    ("SSTI",                   "get",  "/api/courses/?x={{7*7}}", {}),
    ("LDAP",                   "get",  "/api/courses/?x=(uid=*)", {}),
    ("CRLF",                   "get",  "/api/courses/?x=foo%0d%0aSet-Cookie:evil=1", {}),
    ("Path traversal",         "get",  "/api/courses/?f=../../etc/passwd", {}),
    ("Command inj",            "get",  "/api/courses/?c=;ls -la", {}),
    ("XSS",                    "get",  "/api/courses/?q=<script>alert(1)</script>", {}),
    ("URL too long",           "get",  "/api/courses/?x=" + "A"*3000, {}),
    ("Too many params",        "get",  "/api/courses/?" + "&".join(f"p{i}=1" for i in range(100)), {}),
]

print("\n" + "="*70)
print("  HARDENED SECURITY TEST")
print("="*70)

for name, method, url, extra in tests:
    r = getattr(c, method)(url, **extra)
    emoji = "✅" if r.status_code in (400, 403, 414, 415, 429, 431) else "❌"
    print(f"{emoji} {name:<25} → {r.status_code}")

print("\n" + "="*70)