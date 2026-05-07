## Shopping Tracker - Setup Guide

**Status:** 🎉 Initial code complete! Ready to set up and test.

---

## What We've Built

A complete Flask web application with:
- ✅ Database abstraction layer (JSON files)
- ✅ LLM service (Anthropic Claude integration)
- ✅ Receipt processing business logic
- ✅ Flask routes and templates
- ✅ Clean, simple UI with expandable receipts
- ✅ Heavy code comments for learning

---

## Next Steps to Get Running

### 1. Install Dependencies

Open your terminal in the project folder and run:

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install all packages
pip install -r requirements.txt
```

### 2. Create .env File

Copy the example and add your API key:

```bash
# Copy the template
copy .env.example .env    # Windows
# or
cp .env.example .env      # Linux/Mac
```

Then edit `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add it to `.env`:
```
SECRET_KEY=<generated_key_here>
```

### 3. Run the Application

**🎯 EASIEST WAY (Windows):**

Simply double-click: **`run_app.bat`**

That's it! The app will start automatically.

**Alternative Methods:**

**Method 1: Command Prompt**
```bash
# Navigate to project folder
cd C:\Users\Andrzej_Bihun\Projects\ShoppingTracker

# Activate virtual environment
venv\Scripts\activate.bat

# Run app (as a module, not a script)
python -m app.main
```

**Method 2: PowerShell**
```bash
# Navigate to project folder
cd C:\Users\Andrzej_Bihun\Projects\ShoppingTracker

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run app (as a module, not a script)
python -m app.main
```

**Method 3: Git Bash**
```bash
# Navigate to project folder
cd /c/Users/Andrzej_Bihun/Projects/ShoppingTracker

# Activate virtual environment
source venv/Scripts/activate

# Run app (as a module, not a script)
python -m app.main
```

You should see:
```
==================================================
Shopping Tracker - Starting Application
==================================================
[OK] Database initialized: ./data/receipts.json
[OK] LLM service initialized: claude-3-5-sonnet-20241022
[OK] Receipt service initialized
[OK] Routes registered
[OK] Application ready!
[OK] Running on: http://127.0.0.1:5000
[OK] Debug mode: True
Press Ctrl+C to stop the server
==================================================
```

### 4. Open in Browser

Navigate to: **http://localhost:5000**

You should see the Upload page!

---

## Testing the App

### Test 1: Upload Page
1. Go to http://localhost:5000
2. Should see "Upload Receipt" page with file picker
3. Navigation tabs should work (Upload / History)

### Test 2: Upload a Receipt
1. Take a photo of a receipt (or find one online)
2. Click "Choose Receipt Image"
3. Select the file
4. Click "Upload Receipt"
5. Wait for processing (may take 10-20 seconds)
6. Should show success message
7. Should redirect to History page

### Test 3: View History
1. Click "History" tab
2. Should see your uploaded receipt
3. Click on the receipt card
4. Should expand to show items, prices, totals
5. Click again to collapse

---

## Project Structure

```
ShoppingTracker/
│
├── app/                         # Application code
│   ├── __init__.py             # Flask initialization
│   ├── main.py                 # Entry point (RUN THIS)
│   ├── routes.py               # Web routes
│   ├── models.py               # Data models
│   │
│   ├── services/               # Business logic
│   │   ├── llm_service.py     # Claude API integration
│   │   └── receipt_service.py # Receipt processing
│   │
│   └── database/               # Database layer
│       ├── base.py            # Abstract interface
│       └── json_db.py         # JSON implementation
│
├── templates/                  # HTML templates
│   ├── base.html              # Base template
│   ├── upload.html            # Upload page
│   ├── history.html           # History page
│   └── error.html             # Error page
│
├── static/css/                 # Stylesheets
│   └── style.css              # Main CSS
│
├── data/                       # Database (created automatically)
│   └── receipts.json          # Receipts data
│
├── uploads/                    # Temp uploads (created automatically)
│
├── Specification/              # Project docs
│   ├── ProblemStatement.md    # Original requirements
│   ├── ProjectQuestions.md    # Answered questions
│   ├── ProjectSetup.md        # Setup summary
│   └── UIDesign.md            # Visual design
│
├── requirements.txt            # Python dependencies
├── .env                        # Your config (create this!)
├── .env.example               # Config template
├── .gitignore                 # Git ignore rules
├── README.md                  # Project documentation
└── CLAUDE.md                  # AI assistant guide
```

---

## Troubleshooting

### Error: "ANTHROPIC_API_KEY not found"
- Make sure you created `.env` file (not `.env.example`)
- Make sure you added your API key to `.env`
- API key should start with `sk-ant-`

### Error: "Module not found"
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

### Error: "Port 5000 already in use"
- Another program is using port 5000
- Stop that program, or
- Add to `.env`: `FLASK_PORT=5001` (or another port)

### Upload fails with "Invalid file type"
- Only JPG, JPEG, PNG supported
- Check file extension

### LLM returns incorrect data
- The AI is not perfect!
- Try taking a clearer photo
- Make sure text is readable
- We can improve the prompt later

---

## What's Next?

Once you have it running:

1. **Test with various receipts** - See how well it works
2. **Review the code** - Understand how it works
3. **Identify improvements** - What could be better?
4. **Add tests** - Write pytest tests
5. **Enhance features** - Add search, edit, delete, etc.

---

## Architecture Highlights

### Database Abstraction ✨
```python
# Switching to SQL later is just one line change:
# database = JSONDatabase('./data/receipts.json')  # Current
database = SQLDatabase('postgresql://...')  # Future
```

### Service Layer ✨
```python
# Business logic is separate from Flask
# Can be tested without running web server
receipt = receipt_service.process_receipt(file)
```

### Expandable UI ✨
```html
<!-- No JavaScript needed! -->
<details class="receipt-card">
  <summary>Click to expand</summary>
  <div>Hidden content</div>
</details>
```

---

## Learning Opportunities

As you explore the code, notice:

1. **Heavy Comments** - Every function explained
2. **Type Hints** - Clear what data types are expected
3. **Error Handling** - try/except blocks everywhere
4. **Separation of Concerns** - Routes → Services → Database
5. **Design Patterns** - Abstraction, dependency injection

---

## Need Help?

- Read the comments in the code
- Check the Specification/ folder for documentation
- Review CLAUDE.md for architectural guidance
- Look at README.md for user documentation

---

**Ready to start?** Run `python app/main.py` and open http://localhost:5000! 🚀
