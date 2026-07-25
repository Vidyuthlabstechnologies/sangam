import os
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///./test_sangam.db'
os.environ['JWT_SECRET'] = 'test-secret'
os.environ['SARVAM_API_KEY'] = 'sk_gv50556a_Xj5lc0qeDpsi7QkHbSlNCGFC'
os.environ['RAZORPAY_KEY_ID'] = 'rzp_live_TD0msDGLQvTmsJ'
os.environ['RAZORPAY_KEY_SECRET'] = 'n3RVOZSoujb8EdlJVxmNhdmC'
os.environ['EMAIL_API_KEY'] = 'test'
os.environ['SLACK_WEBHOOK_URL'] = 'https://hooks.slack.com/services/test'

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Register and login
email = f"test_{int(__import__('time').time())}@test.ai"
r = client.post('/auth/register', json={'name': 'Test', 'email': email, 'password': 'test123'})
print('Register:', r.status_code)

r = client.post('/auth/login', json={'email': email, 'password': 'test123'})
token = r.json().get('access_token')
print('Login:', r.status_code)
headers = {'Authorization': f'Bearer {token}'}

# Test new endpoints
endpoints = [
    ('PAN Validate', 'POST', '/govstack/pan/validate', {'pan': 'ABCDE1234F'}),
    ('MCA Director', 'POST', '/govstack/mca/director', {'din': '00000001'}),
    ('EPFO Validate', 'POST', '/govstack/epfo/validate', {'uan': '123456789012'}),
    ('DigiLocker Verify', 'POST', '/govstack/digilocker/verify', {'document_id': 'doc123', 'document_type': 'Aadhaar'}),
    ('IEC Validate', 'POST', '/govstack/iec/validate', {'iec': '1234567890'}),
    ('ICEGATE Track', 'POST', '/govstack/icegate/track', {'bill_of_entry': 'BE123456'}),
    ('RERA Validate', 'POST', '/govstack/rera/validate', {'rera_number': 'RERA12345'}),
    ('FSSAI Validate', 'POST', '/govstack/fssai/validate', {'license_number': 'LIC123456'}),
    ('GeM Validate', 'POST', '/govstack/gem/validate', {'gem_registration_id': 'GEM123456'}),
    ('GST Returns', 'POST', '/govstack/gstn/returns', {'gstin': '29AAAAA0000A1Z5', 'return_period': '2024-01'}),
    ('MCA Director', 'POST', '/govstack/mca/director', {'din': '00000001'}),
    ('GST Returns', 'GET', '/govstack/capabilities', None),
]

print('\n=== Testing New GovStack Endpoints ===\n')
for name, method, path, body in endpoints:
    print(f'Testing {name}...')
    try:
        if method == 'POST':
            r = client.post(path, json=body, headers=headers)
        else:
            r = client.get(path)
        print(f'  Status: {r.status_code}')
        if r.status_code == 200:
            print(f'  Keys: {list(r.json().keys())}')
        else:
            print(f'  Error: {r.json() if r.status_code != 500 else r.text[:200]}')
    except Exception as e:
        print(f'  Exception: {e}')
    print()

print('Done!')