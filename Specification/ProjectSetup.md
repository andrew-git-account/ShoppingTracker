# Project Setup Summary

**Date:** May 7, 2026  
**Status:** ✅ Ready to Start Development

This document summarizes all technical decisions made for Shopping Tracker V1.

---

## 🎯 Project Goals

**Primary Goal:** Learn programming with AI assistance, with emphasis on AI/LLM integration

**Learning Focus:**
- Web development fundamentals
- Working with APIs (especially AI/LLM) ⭐ Primary focus
- Database design and management
- Full-stack development
- Python programming

**Development Approach:** 
- Start with minimal features, get something working quickly
- Gradually extend functionality
- Focus on learning and understanding

**Time Commitment:** A few hours per day, no deadline

---

## 🛠️ Technology Stack

### Backend
- **Language:** Python 3.13.0
- **Web Framework:** Flask
  - Reason: Simple, beginner-friendly, lots of tutorials available
  - Good for learning web development fundamentals

### AI/LLM Integration
- **Provider:** Anthropic Claude
- **API:** Claude Vision API (for receipt image processing)
- **Budget:** $10-20/month (regular use, ~300-600 receipts)
- **Status:** ✅ API key obtained

### Database
- **Type:** JSON files (file-based storage)
- **Location:** `./data/` directory
- **Reason:** Simple to understand, easy to debug, no setup required
- **Migration Path:** Can migrate to SQLite/PostgreSQL in V2

### Frontend
- **Style:** Simple but clean
- **Technologies:**
  - HTML5
  - CSS3 (custom styling, no frameworks initially)
  - Jinja2 templates (Flask's template engine)
- **JavaScript:** Not initially (page reloads are fine for V1)

---

## 📦 Version 1 Feature Scope

### ✅ Core Features (Included)
1. **Upload receipt photo**
   - Single image upload per transaction
   - Supported formats: JPG, JPEG, PNG
   - Max file size: 5MB

2. **Extract data using LLM**
   - Item names and prices (mandatory)
   - Store name
   - Purchase date/time
   - Tax amount
   - Discounts/coupons

3. **Store data in JSON database**
   - Save extracted receipt data
   - Keep data forever (no automatic deletion)
   - Do NOT store receipt images (delete after processing)

4. **Display shopping history**
   - Simple list view of all transactions
   - Show all extracted information

### ❌ Optional Features (Deferred to Future)
- Edit extracted data before saving
- Delete transactions
- Search/filter shopping history
- Basic statistics
- Export data (CSV/PDF)
- Multiple receipt images per transaction
- Receipt image preview
- All V2 features (authentication, multi-user, cloud deployment)

---

## 💻 Development Environment

### Operating System
- **V1:** Windows
- **V2:** Linux (future)

### Tools
- **Editor:** Notepad++
- **Version Control:** Git (basic knowledge)
- **Python Version:** 3.13.0 ✅

### Package Management
- **Tool:** pip
- **Virtual Environment:** venv (recommended)

---

## 🧪 Quality & Testing

### Testing
- **Priority:** Very important
- **Approach:** Write tests from the start
- **Framework:** pytest (to be added)

### Code Quality
- **Linters:** Yes, but add later (pylint, flake8)
- **Reason:** Focus on functionality first, improve quality as we learn

### Documentation
- **Code Comments:** Heavy commenting (explain everything for learning)
- **Design Decisions:** Explain WHY we do things a certain way
- **Reason:** Educational project, maximize learning

---

## 🎨 Development Philosophy

### Work Style
- **Approach:** Balance of building from scratch and using libraries
- **Rationale:** Learn fundamentals while being practical

### Error Handling
- **User-Facing:** Show user-friendly messages
- **Backend:** Log detailed errors for debugging
- **Reason:** Good UX while maintaining debuggability

### Project Structure
- **Strategy:** Start simple, refactor later as you learn
- **Rationale:** Don't over-engineer, learn by doing

---

## 📁 Planned Project Structure

```
ShoppingTracker/
│
├── app/                          # Main application code
│   ├── __init__.py              # App initialization
│   ├── main.py                  # Entry point / Flask app
│   ├── routes.py                # Web routes and endpoints
│   ├── llm_service.py           # LLM integration and prompts
│   ├── database.py              # Database operations (JSON CRUD)
│   ├── models.py                # Data models/schemas
│   └── utils.py                 # Helper functions
│
├── static/                      # Static files
│   ├── css/
│   │   └── style.css           # Application styles
│   └── images/
│       └── logo.png            # Application logo
│
├── templates/                   # HTML templates (Jinja2)
│   ├── base.html               # Base template
│   ├── index.html              # Home page
│   ├── upload.html             # Upload receipt page
│   └── history.html            # Shopping history page
│
├── data/                        # JSON database (gitignored)
│   └── receipts.json           # Stored receipt data
│
├── uploads/                     # Temporary uploads (gitignored)
│
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── test_routes.py          # Test web routes
│   ├── test_llm_service.py     # Test LLM integration
│   └── test_database.py        # Test database operations
│
├── Specification/               # Project documentation
│   ├── ProblemStatement.md     # Original requirements
│   ├── ProjectQuestions.md     # Answered questions
│   └── ProjectSetup.md         # This file
│
├── .env                         # Environment variables (gitignored)
├── .env.example                # Example environment file
├── .gitignore                  # Git ignore rules ✅
├── CLAUDE.md                   # AI assistant guidance ✅
├── README.md                   # Project documentation ✅
└── requirements.txt            # Python dependencies (to create)
```

---

## 🔐 Data & Privacy

### Receipt Data Storage
- **Format:** JSON file
- **Location:** `./data/receipts.json`
- **Retention:** Forever (no automatic deletion)
- **Fields Stored:**
  - Transaction ID (unique identifier)
  - Upload date/time
  - Store name
  - Purchase date/time
  - Items list (name, price per item)
  - Subtotal
  - Tax amount
  - Discounts/coupons
  - Total amount

### Receipt Images
- **Storage:** Temporary only (in `./uploads/` during processing)
- **Deletion:** Automatically deleted after successful data extraction
- **Reason:** Save disk space, privacy

---

## 🚀 Development Roadmap

### Phase 1: Setup (Current)
- [x] Answer all project questions ✅
- [ ] Create project structure (folders)
- [ ] Create `requirements.txt`
- [ ] Create `.env.example`
- [ ] Set up virtual environment
- [ ] Install dependencies

### Phase 2: Basic Flask App
- [ ] Create minimal Flask app
- [ ] Set up routing
- [ ] Create base HTML template
- [ ] Test that server runs

### Phase 3: File Upload
- [ ] Create upload form (HTML)
- [ ] Implement file upload endpoint
- [ ] Validate file type and size
- [ ] Save uploaded file temporarily

### Phase 4: LLM Integration
- [ ] Install Anthropic SDK
- [ ] Create LLM service module
- [ ] Design prompt for receipt extraction
- [ ] Test with sample receipts
- [ ] Parse LLM response to structured data

### Phase 5: Database Layer
- [ ] Design JSON data schema
- [ ] Create database module (CRUD operations)
- [ ] Implement save receipt function
- [ ] Implement list receipts function
- [ ] Test with sample data

### Phase 6: Display History
- [ ] Create history page template
- [ ] Implement history route
- [ ] Display all receipts
- [ ] Format data nicely

### Phase 7: Integration & Testing
- [ ] Connect all components (upload → LLM → database → display)
- [ ] Write unit tests
- [ ] Test with real receipts
- [ ] Fix bugs and improve prompts

### Phase 8: Polish
- [ ] Add CSS styling
- [ ] Improve error messages
- [ ] Add loading indicators
- [ ] User experience improvements
- [ ] Documentation updates

---

## 🎓 Learning Objectives Mapping

### Web Development (Flask)
- Setting up a web server
- Routing and handling HTTP requests
- Template rendering with Jinja2
- Form handling and file uploads
- Session management

### AI/LLM Integration ⭐
- Working with Anthropic Claude API
- Prompt engineering for data extraction
- Handling vision/image inputs
- Parsing structured data from LLM responses
- Error handling with AI services

### Database Management
- Designing data schemas
- CRUD operations (Create, Read, Update, Delete)
- Working with JSON files
- Data validation

### Full-Stack Development
- Frontend-backend communication
- User experience considerations
- Error handling across layers
- Project structure and organization

### Python Programming
- Modern Python features (3.13)
- Working with libraries (Flask, Anthropic SDK)
- File I/O operations
- Testing with pytest
- Virtual environments and dependencies

---

## 📚 Key Dependencies

### Required Packages
```
Flask>=3.0.0              # Web framework
anthropic>=0.25.0         # Anthropic Claude SDK
python-dotenv>=1.0.0      # Environment variables
Pillow>=10.0.0            # Image processing
```

### Development Packages
```
pytest>=7.4.0             # Testing framework
pytest-flask>=1.3.0       # Flask testing utilities
```

### To be added later
```
pylint>=3.0.0             # Code quality
black>=23.0.0             # Code formatter
```

---

## 🔑 Environment Variables

### Required in .env file
```bash
# Anthropic API Configuration
ANTHROPIC_API_KEY=your_api_key_here

# Flask Configuration
FLASK_APP=app.main
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

# Application Settings
UPLOAD_FOLDER=./uploads
DATA_FOLDER=./data
MAX_UPLOAD_SIZE=5242880  # 5MB in bytes
ALLOWED_EXTENSIONS=jpg,jpeg,png

# LLM Configuration
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_MAX_TOKENS=4096
```

---

## 🎯 Success Criteria for V1

Version 1 will be considered complete when:

1. ✅ User can upload a receipt image
2. ✅ Claude successfully extracts receipt data (items, prices, store, date, tax, discounts)
3. ✅ Data is saved to JSON file
4. ✅ User can view all past receipts in history page
5. ✅ Application has basic but clean UI
6. ✅ Code is well-commented for learning
7. ✅ Basic tests are passing
8. ✅ README has usage instructions

---

## 🔮 Future (Version 2)

Deferred to later:
- User authentication (login/password)
- Multi-user support
- Migration to relational database (PostgreSQL)
- Cloud deployment on Azure
- Advanced features (search, filter, statistics, export)
- Mobile responsive design
- More robust error handling
- Production-ready security

---

## ✅ Status: Ready to Start!

All decisions made. Let's begin development! 🚀

**Next Step:** Create project structure and requirements.txt
