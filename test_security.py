# test_security.py
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dems_backend.settings')
django.setup()

from accounts.face_service import extract_embedding, compare_embeddings, verify_against_reference

def banner(t): print(f"\n{'='*60}\n  {t}\n{'='*60}")

def load(path):
    import base64
    with open(path, 'rb') as f:
        return 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()

banner("SECURITY TEST")

# Ask for two face images
p1 = input("Path to face 1 (student's real face): ").strip()
p2 = input("Path to face 2 (different person): ").strip()

if not os.path.exists(p1):
    print(f"❌ File not found: {p1}")
    exit(1)
if not os.path.exists(p2):
    print(f"❌ File not found: {p2}")
    exit(1)

banner("Extracting embeddings")
r1 = extract_embedding(load(p1))
r2 = extract_embedding(load(p2))

print(f"Face 1 detected: {r1['success']}  ({r1.get('error') or 'OK'})")
print(f"Face 2 detected: {r2['success']}  ({r2.get('error') or 'OK'})")

if not (r1['success'] and r2['success']):
    print("\n❌ One or both faces couldn't be detected. Try clearer images.")
    exit(1)

banner("TEST A — Same person should MATCH")
same = verify_against_reference(load(p1), r1['embedding'])
print(f"  Verified:   {same['verified']}")
print(f"  Confidence: {same['confidence']}")
print(f"  Distance:   {1 - same['confidence']:.3f}")

banner("TEST B — Different person should NOT MATCH")
diff = verify_against_reference(load(p2), r1['embedding'])
print(f"  Verified:   {diff['verified']}")
print(f"  Confidence: {diff['confidence']}")
print(f"  Distance:   {1 - diff['confidence']:.3f}")

banner("VERDICT")
if same['verified'] and not diff['verified']:
    print("  🎉 PASS — Same face matches, different face rejected")
    print("  ✅ Your security system is functioning correctly")
elif not same['verified']:
    print("  ⚠️ FAIL — Same person didn't match (lighting/angle issue)")
elif diff['verified']:
    print("  🚨 SECURITY BUG — Different person matched!")
    print("  Check your compare_embeddings threshold")
else:
    print("  ❓ Unexpected result — review the numbers above")

print()