# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shopping Tracker is an **educational project** for learning programming with AI assistance. The project is being developed by a beginner programmer, so code explanations should be clear and educational.

**Goal:** Track shopping expenses by uploading photos of receipts, extracting item details using LLM, and storing/displaying the data.

### Core Workflow
1. User uploads a photo of a receipt
2. System sends the image to an LLM
3. LLM extracts items and prices
4. System stores data in database
5. System displays the data to the user

## Development Roadmap

### Version 1 - Proof of Concept (✅ Core Implemented)
**Status**: Core infrastructure complete, ready for receipt uploads with API key

**Implemented**:
- ✅ Flask web application with proper architecture
- ✅ Database abstraction layer (JSON files)
- ✅ LLM service integration (Anthropic Claude)
- ✅ Receipt processing service (business logic)
- ✅ Data models (Receipt, ReceiptItem)
- ✅ Web routes (upload, history)
- ✅ HTML templates with expandable receipts
- ✅ Responsive CSS styling
- ✅ Flash messages for user feedback
- ✅ Sample receipts for testing

**Pending**:
- Testing with real receipt uploads (waiting for API key approval)
- Unit tests
- Error handling improvements

### Version 2 - Deployable Version (Future)
- Deployable web application
- User/password authentication
- Relational database (PostgreSQL on Azure)
- Edit/delete functionality
- Search and filters
- Analytics dashboard

## Technology Stack

**Implemented Stack:**
- **Python**: 3.13.0
- **Web Framework**: Flask 3.0.3
- **LLM Integration**: Anthropic Claude API (anthropic==0.34.2)
  - ⚠️ **Important**: Use `anthropic==0.34.2` and `httpx<0.28` for compatibility
- **Database**: JSON files (JSONDatabase implementation in V1)
- **Frontend**: HTML5, CSS3, Jinja2 templates (no JavaScript required)

## Development Guidelines

### For Beginners
- **Explain your code**: Add comments explaining non-obvious logic
- **Use simple patterns first**: Don't over-engineer; prefer straightforward solutions
- **Break down complex tasks**: Split large features into smaller, testable pieces
- **Educational focus**: When suggesting code, explain *why* you're doing it that way

### Project Structure (Implemented)
```
ShoppingTracker/
├── app/                         # Application code
│   ├── __init__.py             # Flask initialization
│   ├── main.py                 # Entry point (run as module: python -m app.main)
│   ├── routes.py               # Web routes/endpoints
│   ├── models.py               # Data models (Receipt, ReceiptItem)
│   ├── services/               # Business logic layer
│   │   ├── llm_service.py     # Claude API integration
│   │   └── receipt_service.py # Receipt processing
│   └── database/               # Database abstraction layer
│       ├── base.py            # Abstract interface
│       └── json_db.py         # JSON implementation
├── static/css/                 # Stylesheets
│   └── style.css              # Main CSS
├── templates/                  # HTML templates (Jinja2)
│   ├── base.html              # Base template
│   ├── upload.html            # Upload page
│   ├── history.html           # History page
│   └── error.html             # Error page
├── data/                       # JSON database (gitignored)
│   └── receipts.json          # User receipt data
├── uploads/                    # Temporary files (gitignored)
├── tests/                      # Test files
├── Specification/              # Project documentation
│   ├── ProblemStatement.md
│   ├── ProjectQuestions.md
│   ├── ProjectSetup.md
│   └── UIDesign.md
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (gitignored)
├── .env.example               # Config template
├── run_app.bat                # Windows run script
└── run_app.ps1                # PowerShell run script
```

### Key Implementation Notes

1. **Image Processing**: You'll need to handle file uploads and potentially convert images to formats the LLM accepts
2. **LLM Prompt Engineering**: Design prompts to reliably extract structured data (item names, quantities, prices) from receipt images
3. **Data Storage (V1)**: Use JSON files or SQLite - easy to set up and sufficient for local testing
4. **Error Handling**: Receipts can be unclear, handle cases where LLM can't extract data

## Sample Data

The repository includes sample receipts in `data/receipts.json` for testing:
- **Walmart** receipt (May 5, 2026) - $17.04 total, 4 items
- **Target** receipt (May 7, 2026) - $31.95 total, 5 items

These allow testing the History page without needing an API key.

## Specification Location

Full project requirements and decisions:
- `Specification/ProblemStatement.md` - Original requirements
- `Specification/ProjectQuestions.md` - Answered setup questions
- `Specification/ProjectSetup.md` - Technical decisions
- `Specification/UIDesign.md` - Visual design specification

## Common Commands

### Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate.bat          # Windows CMD
venv\Scripts\Activate.ps1          # Windows PowerShell
source venv/Scripts/activate       # Git Bash

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env             # Then edit .env with API key
```

### Running the Application
```bash
# IMPORTANT: Run as a module, not as a script
python -m app.main

# OR use the convenience scripts:
run_app.bat                        # Windows (double-click or run from CMD)
```

**Note**: Do NOT run `python app/main.py` - this causes import errors due to relative imports. Always use `python -m app.main`.

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Test setup
python test_setup.py
```

## Architecture Highlights

### Database Abstraction Layer
- Uses abstract base class (`Database`) with concrete implementations
- Easy to swap JSON files for SQL later by changing one line
- All database operations go through the abstraction
- Location: `app/database/`

### Service Layer Pattern
- Business logic separated from web routes
- `receipt_service.py` orchestrates the workflow
- `llm_service.py` handles Claude API integration
- Routes are thin - just HTTP handling
- Location: `app/services/`

### Template Structure
- `base.html` provides navigation, flash messages, common structure
- Child templates extend base and override content block
- Uses native HTML `<details>` tags for expandable receipts (no JS needed)
- Flask configured to find templates at project root: `templates/`

## Important Technical Notes

### Windows Encoding Issues
- Avoid Unicode characters (✓, ✗, 🛒) in print statements
- Use `[OK]`, `[FAIL]`, `[WARN]` instead
- Windows console (cp1252) doesn't handle Unicode well

### Flask Configuration
When running as a module, explicitly set template and static folders:
```python
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    template_folder=os.path.join(project_root, 'templates'),
    static_folder=os.path.join(project_root, 'static')
)
```

### Dependency Versions
Critical for compatibility:
- `anthropic==0.34.2` (not 0.39.0 - has issues with Python 3.13)
- `httpx<0.28` (0.28+ breaks anthropic client)
- `Flask==3.0.3`

### Jinja2 Templates
- Keep templates clean - avoid complex inline conditionals
- HTML comments are fine, but keep Jinja syntax simple
- Test templates by starting with minimal version, then adding features
- Common error: unclosed `{% if %}` blocks

## Notes for AI Assistance

- This is a **learning project** - prioritize clarity over cleverness
- The developer is **not experienced** - provide context and explanations
- Start simple for V1, don't jump to V2 features prematurely
- Focus on getting a working prototype before optimization
- **Heavy commenting required** - explain WHY, not just WHAT
- Avoid emojis and Unicode in Python print statements (Windows encoding issues)
- When creating templates, start minimal and test before adding complexity

## Common Issues & Solutions

### Import Errors
**Problem**: `ImportError: attempted relative import with no known parent package`
**Solution**: Run as module: `python -m app.main` (not `python app/main.py`)

### Template Not Found
**Problem**: `jinja2.exceptions.TemplateNotFound`
**Solution**: Ensure Flask app specifies template_folder pointing to project root

### Anthropic API Errors
**Problem**: `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`
**Solution**: Downgrade to `anthropic==0.34.2` and `httpx<0.28`

### Template Syntax Errors
**Problem**: `Unexpected end of template` or unclosed blocks
**Solution**: Verify all `{% if %}`, `{% for %}`, `{% block %}` have matching end tags
