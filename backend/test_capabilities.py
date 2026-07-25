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

# Test capabilities endpoint
r = client.get('/govstack/capabilities')
print('Capabilities endpoint:', r.status_code)
if r.status_code == 200:
    data = r.json()
    print('Capabilities count:', len(data.get('capabilities', [])))
    for c in data.get('capabilities', []):
        print('  -', c['name'])
else:
    print('Error:', r.text)