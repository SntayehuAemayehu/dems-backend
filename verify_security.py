# verify_security.py
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dems_backend.settings')
django.setup()

from django.conf import settings
from django.test import Client, RequestFactory
from django.utils import timezone
import json

print("=" * 70)
print("  SECURITY MIDDLEWARE VERIFICATION")
print("=" * 70)

# ---------- 1. Check middleware list ----------
print("\n📋 MIDDLEWARE in settings.py:")
for m in settings.MIDDLEWARE:
    marker = "✅" if 'comprehensive_security' in m else "  "
    print(f"  {marker} {m}")

assert any('comprehensive_security' in m for m in settings.MIDDLEWARE), \
    "❌ ComprehensiveSecurityMiddleware NOT in MIDDLEWARE!"
print("\n✅ ComprehensiveSecurityMiddleware is ACTIVE")

# ---------- 2. Confirm duplicates are removed ----------
dupes = [
    'middleware.security_headers.SecurityHeadersMiddleware',
    'middleware.rate_limit.RateLimitMiddleware',
    'middleware.security_middleware.SQLInjectionMiddleware',
    'middleware.security_middleware.SecureCookieMiddleware',
]
for d in dupes:
    if d in settings.MIDDLEWARE:
        print(f"⚠️  Duplicate still present: {d}")
    else:
        print(f"✅ Removed duplicate: {d}")

# ---------- 3. Test each protection ----------
client = Client()

print("\n" + "=" * 70)
print("  TESTING EACH PROTECTION")
print("=" * 70)

# 1. Bot UA
print("\n1️⃣  Bot User-Agent blocking...")
r = client.get('/api/courses/', HTTP_USER_AGENT='sqlmap/1.0')
print(f"   Status: {r.status_code}  (expect 403)")
assert r.status_code == 403, "❌ Bot UA not blocked!"
print("   ✅ Bot blocked")

# 2. XSS
print("\n2️⃣  XSS pattern detection...")
r = client.get('/api/courses/?search=<script>alert(1)</script>')
print(f"   Status: {r.status_code}  (expect 403)")
assert r.status_code == 403, "❌ XSS not blocked!"
print("   ✅ XSS blocked")

# 3. SQL injection
print("\n3️⃣  SQL injection detection...")
r = client.get("/api/courses/?id=1' OR '1'='1")
print(f"   Status: {r.status_code}  (expect 403)")
assert r.status_code == 403, "❌ SQLi not blocked!"
print("   ✅ SQLi blocked")

# 4. Path traversal
print("\n4️⃣  Path traversal detection...")
r = client.get('/api/courses/?file=../../etc/passwd')
print(f"   Status: {r.status_code}  (expect 403)")
assert r.status_code == 403, "❌ Path traversal not blocked!"
print("   ✅ Path traversal blocked")

# 5. Command injection
print("\n5️⃣  Command injection detection...")
r = client.get('/api/courses/?cmd=;ls -la')
print(f"   Status: {r.status_code}  (expect 403)")
assert r.status_code == 403, "❌ Command injection not blocked!"
print("   ✅ Command injection blocked")

# 6. Invalid HTTP method
print("\n6️⃣  Invalid HTTP method...")
r = client.generic('TRACE', '/api/courses/')
print(f"   Status: {r.status_code}  (expect 405)")
assert r.status_code == 405, "❌ Invalid method not blocked!"
print("   ✅ Invalid method blocked")

# 7. Security headers
print("\n7️⃣  Security headers...")
r = client.get('/api/courses/')
required = ['Strict-Transport-Security', 'X-Content-Type-Options',
            'X-Frame-Options', 'X-XSS-Protection', 'Content-Security-Policy',
            'Referrer-Policy', 'Permissions-Policy']
for h in required:
    assert h in r, f"❌ Missing header: {h}"
    print(f"   ✅ {h}: {r[h][:50]}...")

print("\n" + "=" * 70)
print("  ✅✅✅ ALL SECURITY PROTECTIONS VERIFIED ✅✅✅")
print("=" * 70)