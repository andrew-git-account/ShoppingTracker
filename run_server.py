from dotenv import load_dotenv
load_dotenv(override=True)
import sys
sys.stdout = open('server.log', 'w', buffering=1)
sys.stderr = sys.stdout
from app.main import create_app
app = create_app()
app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
