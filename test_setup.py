"""
Quick test to verify setup without calling the LLM.
Run this to make sure everything is working before adding receipts.
"""

import sys
import os

print("=" * 50)
print("Testing Shopping Tracker Setup")
print("=" * 50)

# Test 1: Check Python version
print("\n1. Python Version:")
print(f"   [OK] Python {sys.version.split()[0]}")

# Test 2: Check imports
print("\n2. Testing imports...")
try:
    from flask import Flask
    print("   [OK] Flask imported")
except ImportError as e:
    print(f"   [FAIL] Flask import failed: {e}")
    sys.exit(1)

try:
    from anthropic import Anthropic
    print("   [OK] Anthropic imported")
except ImportError as e:
    print(f"   [FAIL] Anthropic import failed: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    print("   [OK] python-dotenv imported")
except ImportError as e:
    print(f"   [FAIL] python-dotenv import failed: {e}")
    sys.exit(1)

try:
    from PIL import Image
    print("   [OK] Pillow imported")
except ImportError as e:
    print(f"   [FAIL] Pillow import failed: {e}")
    sys.exit(1)

# Test 3: Check .env file
print("\n3. Checking .env file...")
if os.path.exists('.env'):
    print("   [OK] .env file exists")
    load_dotenv()
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key and api_key != 'your_anthropic_api_key_here':
        print("   [OK] ANTHROPIC_API_KEY is set")
        print(f"   Key starts with: {api_key[:10]}...")
    else:
        print("   [WARN] ANTHROPIC_API_KEY not set (you'll need this to upload receipts)")
else:
    print("   [FAIL] .env file not found")
    sys.exit(1)

# Test 4: Check database
print("\n4. Checking database...")
try:
    from app.database import JSONDatabase
    db = JSONDatabase('./data/receipts.json')
    receipts = db.get_all_receipts()
    print(f"   [OK] Database initialized")
    print(f"   [OK] Found {len(receipts)} sample receipts")
except Exception as e:
    print(f"   [FAIL] Database error: {e}")
    sys.exit(1)

# Test 5: Check models
print("\n5. Testing models...")
try:
    from app.models import Receipt, ReceiptItem
    item = ReceiptItem("Test Item", 5.99, 1)
    receipt = Receipt(items=[item], store_name="Test Store")
    is_valid, error = receipt.validate()
    if is_valid:
        print("   [OK] Models working correctly")
    else:
        print(f"   [FAIL] Model validation failed: {error}")
except Exception as e:
    print(f"   [FAIL] Model error: {e}")
    sys.exit(1)

# Test 6: Check Flask app
print("\n6. Testing Flask app...")
try:
    from app.main import create_app
    app = create_app()
    print("   [OK] Flask app created successfully")
    print(f"   [OK] Routes registered: {len(app.url_map._rules)} routes")
except Exception as e:
    print(f"   [FAIL] Flask app error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Success!
print("\n" + "=" * 50)
print("SUCCESS! All tests passed!")
print("=" * 50)
print("\nSummary:")
print(f"   - Python: {sys.version.split()[0]}")
print(f"   - Sample receipts in database: {len(receipts)}")
print(f"   - Flask routes: {len(app.url_map._rules)}")
api_configured = 'Yes' if (api_key and api_key != 'your_anthropic_api_key_here') else 'No (add to .env)'
print(f"   - API key configured: {api_configured}")

print("\nReady to run!")
print("   Run: python app/main.py")
print("   Then visit: http://localhost:5000")
print("\n" + "=" * 50)
