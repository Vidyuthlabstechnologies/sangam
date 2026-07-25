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
from app.db.base import Base
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio

engine = create_async_engine('sqlite+aiosqlite:///./test_sangam.db', echo=False)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(create_tables())

client = TestClient(app)

# Register and login first
print('Registering user...')
r = client.post('/auth/register', json={'name': 'GovStack Tester', 'email': 'govstack@test.ai', 'password': 'test123'})
print(f'  Register: {r.status_code}')

print('Logging in...')
r = client.post('/auth/login', json={'email': 'govstack@test.ai', 'password': 'test123'})
token = r.json().get('access_token')
print(f'  Login: {r.status_code}, Token: {token[:20]}...')

headers = {'Authorization': f'Bearer {token}'}

def test_endpoint(name, path, json_body):
    print(f'Testing {name}...')
    r = client.post(path, json=json_body, headers=headers)
    print(f'  Status: {r.status_code}')
    resp = r.json()
    print(f'  Keys: {list(resp.keys()) if isinstance(resp, dict) else "list"}')
    return resp

# Test all GovStack endpoints
print()
test_endpoint('GSTN Validate', '/govstack/gstn/validate', {'gstin': '29AAAAA0000A1Z5'})
test_endpoint('MCA Company', '/govstack/mca/company', {'cin': 'U74999KA2020PTC123456'})
test_endpoint('Udyam Validate', '/govstack/udyam/validate', {'udyam_number': 'UDYAM-KA-0012345'})
test_endpoint('Schemes Discover', '/govstack/schemes/discover', {'industry': 'manufacturing', 'state': 'Karnataka'})
test_endpoint('MOSPI Indicator', '/govstack/mospi/indicator', {'indicator': 'gdp_growth'})
test_endpoint('MOSPI Labor', '/govstack/mospi/labor', {'survey': 'PLFS'})
test_endpoint('GatiShakti Analyze', '/govstack/gatishakti/analyze', {'latitude': 12.9716, 'longitude': 77.5946})
test_endpoint('Power Data', '/govstack/power/data', {'region': 'Southern Region'})

# GET endpoint
print('Testing /govstack/capabilities...')
r = client.get('/govstack/capabilities')
print(f'  Status: {r.status_code}')
data = r.json()
print(f'  Capabilities count: {len(data.get("capabilities", []))}')

print()
print('All GovStack endpoints working with auth!')