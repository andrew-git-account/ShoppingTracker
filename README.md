# Shopping Tracker

A web application that helps you track your shopping expenses by automatically extracting data from receipt photos using AI.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
- [Project Roadmap](#project-roadmap)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Development](#development)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Overview

Shopping Tracker is an educational project designed to help users monitor their spending habits by digitizing physical shopping receipts. Simply take a photo of your receipt, upload it to the application, and let AI extract the items and prices automatically. All your shopping data is stored locally and displayed in an easy-to-read format.

**Target Audience:** This project is built as a learning exercise in:
- Web application development
- AI/LLM integration
- Database management
- Full-stack development

## Features

### Current Version (Planned - V1: Proof of Concept)

- **Receipt Upload**: Upload photos of shopping receipts
- **AI-Powered Extraction**: Automatically extract item names and prices using Large Language Models (LLM)
- **Local Storage**: Store all shopping data locally on your computer
- **Data Visualization**: View your shopping history in a user-friendly interface
- **No Authentication**: Simple, single-user setup for local use

### Future Version (V2: Deployable Application)

- **Cloud Deployment**: Deploy on external servers for access anywhere
- **User Authentication**: Secure login with username/password
- **Relational Database**: Robust data storage with PostgreSQL or MySQL
- **Multi-User Support**: Multiple users can track their own shopping
- **Advanced Analytics**: Spending trends, category breakdowns, and more
- **Mobile Responsive**: Optimized for mobile devices

## How It Works

1. **Upload Receipt**: User takes a photo of their receipt and uploads it through the web interface
2. **AI Processing**: The application sends the image to a Large Language Model (LLM)
3. **Data Extraction**: The LLM analyzes the receipt and returns structured data:
   - Item names
   - Quantities
   - Individual prices
   - Total amount
   - Store name (if visible)
   - Date (if visible)
4. **Data Storage**: Extracted information is saved to the local database
5. **Display**: User can view all their shopping transactions in a dashboard

## Project Roadmap

### Phase 1: Proof of Concept ✓ (In Progress)

**Goal:** Create a working prototype that demonstrates core functionality

- [ ] Set up basic web application framework
- [ ] Implement file upload functionality
- [ ] Integrate LLM API for receipt processing
- [ ] Create prompt engineering for accurate data extraction
- [ ] Implement local file-based database
- [ ] Build basic user interface for viewing shopping history
- [ ] Test with various receipt formats

**Technical Decisions:**
- Run entirely on localhost
- No user authentication required
- File-based storage (JSON or SQLite)
- Minimal UI/UX - focus on functionality

### Phase 2: Deployable Application (Future)

**Goal:** Transform the prototype into a production-ready application

- [ ] Add user registration and authentication
- [ ] Migrate to relational database (PostgreSQL/MySQL)
- [ ] Implement proper error handling and logging
- [ ] Add data validation and security measures
- [ ] Create responsive UI design
- [ ] Set up deployment pipeline
- [ ] Deploy to cloud platform (Heroku, AWS, Azure, etc.)
- [ ] Add spending analytics and reports
- [ ] Implement data export functionality

## Technology Stack

### Backend
- **Programming Language**: Python 3.8+
- **Web Framework**: Flask or FastAPI
  - *Flask*: Lightweight, beginner-friendly, great for learning
  - *FastAPI*: Modern, fast, automatic API documentation
- **LLM Integration**: 
  - OpenAI API (GPT-4 Vision) - Recommended for receipt OCR
  - Anthropic Claude API (Claude with vision)
  - Or any vision-capable LLM

### Frontend
- **HTML5**: Structure
- **CSS3**: Styling
- **JavaScript**: Interactivity
- **Template Engine**: Jinja2 (if using Flask)

### Database
- **Version 1**: JSON files or SQLite
- **Version 2**: PostgreSQL or MySQL

### Development Tools
- **Version Control**: Git
- **Package Management**: pip, virtualenv
- **Testing**: pytest or unittest
- **Code Quality**: pylint, black (formatter)

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8 or higher**
  - Download from [python.org](https://www.python.org/downloads/)
  - Verify installation: `python --version`

- **pip** (Python package installer)
  - Usually comes with Python
  - Verify installation: `pip --version`

- **Git** (for version control)
  - Download from [git-scm.com](https://git-scm.com/)
  - Verify installation: `git --version`

- **LLM API Key** (you'll need one of these):
  - OpenAI API key from [platform.openai.com](https://platform.openai.com/)
  - Anthropic API key from [console.anthropic.com](https://console.anthropic.com/)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ShoppingTracker.git
cd ShoppingTracker
```

### 2. Create a Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

*Note: Once requirements.txt is created, it will contain packages like:*
- Flask or FastAPI
- python-dotenv (for environment variables)
- openai or anthropic (for LLM integration)
- Pillow (for image processing)
- pytest (for testing)

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# .env file
LLM_API_KEY=your_api_key_here
LLM_PROVIDER=openai  # or anthropic
DATABASE_PATH=./data/shopping.db
UPLOAD_FOLDER=./uploads
MAX_UPLOAD_SIZE=5242880  # 5MB in bytes
```

**Important:** Never commit your `.env` file to version control. It's already in `.gitignore`.

## Configuration

### LLM Selection

The application supports multiple LLM providers. Configure your preferred provider in the `.env` file:

**For OpenAI (GPT-4 Vision):**
```
LLM_PROVIDER=openai
LLM_API_KEY=sk-...your-openai-key...
LLM_MODEL=gpt-4-vision-preview
```

**For Anthropic Claude:**
```
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...your-anthropic-key...
LLM_MODEL=claude-3-opus-20240229
```

### Database Configuration

**SQLite (Recommended for V1):**
```
DATABASE_TYPE=sqlite
DATABASE_PATH=./data/shopping.db
```

**JSON Files:**
```
DATABASE_TYPE=json
DATABASE_PATH=./data/shopping.json
```

## Usage

### Starting the Application

1. **Activate your virtual environment** (if not already activated):
   ```bash
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

2. **Run the application**:
   ```bash
   python app/main.py
   # OR if using Flask
   flask run
   # OR if using FastAPI
   uvicorn app.main:app --reload
   ```

3. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   # OR
   http://127.0.0.1:5000
   ```

### Using the Application

#### 1. Upload a Receipt

- Click the "Upload Receipt" button
- Select a clear photo of your receipt
- Supported formats: JPG, JPEG, PNG
- Maximum file size: 5MB

#### 2. Wait for Processing

- The application will send your receipt to the LLM
- Processing typically takes 5-15 seconds
- You'll see a loading indicator

#### 3. Review Extracted Data

- The LLM will extract:
  - Store name
  - Purchase date
  - List of items with prices
  - Total amount
- **Review the data** - AI isn't perfect!
- Edit any incorrect information

#### 4. Save Transaction

- Click "Save" to store the transaction
- The data is now in your local database

#### 5. View Shopping History

- Navigate to "History" or "Dashboard"
- See all your past shopping transactions
- Filter by date, store, or amount

### Tips for Best Results

- **Take clear photos**: Ensure receipt text is readable
- **Good lighting**: Avoid shadows and glare
- **Flat surface**: Flatten crumpled receipts before photographing
- **Complete receipt**: Capture the entire receipt in frame
- **Recent receipts**: Faded receipts may not process well

## Project Structure

```
ShoppingTracker/
│
├── app/                          # Main application code
│   ├── __init__.py              # App initialization
│   ├── main.py                  # Entry point / Flask app
│   ├── routes.py                # Web routes and endpoints
│   ├── llm_service.py           # LLM integration and prompts
│   ├── database.py              # Database operations (CRUD)
│   ├── models.py                # Data models/schemas
│   └── utils.py                 # Helper functions
│
├── static/                      # Static files (served to browser)
│   ├── css/
│   │   └── style.css           # Application styles
│   ├── js/
│   │   └── main.js             # Frontend JavaScript
│   └── images/
│       └── logo.png            # Application logo
│
├── templates/                   # HTML templates (Jinja2)
│   ├── base.html               # Base template
│   ├── index.html              # Home page
│   ├── upload.html             # Upload receipt page
│   └── history.html            # Shopping history page
│
├── data/                        # Local database storage (V1)
│   └── shopping.db             # SQLite database (gitignored)
│
├── uploads/                     # Temporary receipt uploads (gitignored)
│
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── test_routes.py          # Test web routes
│   ├── test_llm_service.py     # Test LLM integration
│   └── test_database.py        # Test database operations
│
├── Specification/               # Project documentation
│   └── ProblemStatement.md     # Original requirements
│
├── .env                         # Environment variables (gitignored)
├── .env.example                # Example environment file
├── .gitignore                  # Git ignore rules
├── CLAUDE.md                   # Guidance for AI assistants
├── README.md                   # This file
├── requirements.txt            # Python dependencies
└── LICENSE                     # Project license
```

## Development

### Setting Up Development Environment

1. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Install pre-commit hooks** (optional):
   ```bash
   pre-commit install
   ```

### Code Style

This project follows Python best practices:

- **PEP 8**: Python style guide
- **Type hints**: Use type annotations where appropriate
- **Docstrings**: Document all functions and classes
- **Line length**: Maximum 88 characters (Black formatter default)

**Format code with Black**:
```bash
black app/
```

**Check code quality with pylint**:
```bash
pylint app/
```

### Adding a New Feature

1. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Write tests for your feature

4. Run tests to ensure nothing broke

5. Commit your changes:
   ```bash
   git add .
   git commit -m "Add: description of your feature"
   ```

6. Push to your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

## Testing

### Running Tests

**Run all tests**:
```bash
pytest
```

**Run with coverage report**:
```bash
pytest --cov=app tests/
```

**Run specific test file**:
```bash
pytest tests/test_routes.py
```

**Run specific test function**:
```bash
pytest tests/test_routes.py::test_upload_receipt
```

### Writing Tests

Example test structure:

```python
# tests/test_llm_service.py
import pytest
from app.llm_service import extract_receipt_data

def test_extract_receipt_data():
    """Test that LLM service extracts data correctly"""
    # Arrange
    mock_image = "path/to/test/receipt.jpg"
    
    # Act
    result = extract_receipt_data(mock_image)
    
    # Assert
    assert result is not None
    assert "items" in result
    assert "total" in result
```

## Troubleshooting

### Common Issues

#### 1. Module Not Found Error

**Error**: `ModuleNotFoundError: No module named 'flask'`

**Solution**: 
```bash
# Ensure virtual environment is activated
pip install -r requirements.txt
```

#### 2. LLM API Key Invalid

**Error**: `Authentication failed` or `Invalid API key`

**Solution**:
- Check your `.env` file has the correct API key
- Verify the API key is valid in your provider's dashboard
- Ensure no extra spaces or quotes in the `.env` file

#### 3. Image Upload Fails

**Error**: `File too large` or `Invalid file type`

**Solution**:
- Check file size (must be under 5MB)
- Ensure file is JPG, JPEG, or PNG format
- Try compressing the image

#### 4. Database Connection Error

**Error**: `sqlite3.OperationalError: unable to open database file`

**Solution**:
```bash
# Create data directory if it doesn't exist
mkdir data
# Check file permissions
chmod 755 data/
```

#### 5. Port Already in Use

**Error**: `Address already in use: Port 5000`

**Solution**:
```bash
# Find and kill process using port 5000
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:5000 | xargs kill -9

# Or use a different port
flask run --port 5001
```

### Getting Help

If you encounter issues not listed here:

1. Check the [Issues](https://github.com/yourusername/ShoppingTracker/issues) page
2. Search for similar problems
3. Create a new issue with:
   - Detailed description of the problem
   - Steps to reproduce
   - Error messages (full traceback)
   - Your environment (OS, Python version)

## Contributing

Contributions are welcome! This is a learning project, so don't hesitate to suggest improvements or ask questions.

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/AmazingFeature`
3. **Commit your changes**: `git commit -m 'Add some AmazingFeature'`
4. **Push to the branch**: `git push origin feature/AmazingFeature`
5. **Open a Pull Request**

### Contribution Guidelines

- Write clear, descriptive commit messages
- Add tests for new features
- Update documentation as needed
- Follow the existing code style
- Be respectful and constructive in discussions

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

### Learning Resources

This project was built while learning from:
- [Flask Documentation](https://flask.palletsprojects.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Python Official Tutorial](https://docs.python.org/3/tutorial/)

### Inspiration

- Receipt tracking apps like Expensify and Receipt Bank
- The growing accessibility of AI/LLM technology for everyday applications

### Technologies Used

- **Python**: The programming language
- **Flask/FastAPI**: Web framework
- **OpenAI/Anthropic**: LLM providers for receipt processing
- **SQLite**: Local database

---

## Project Status

**Current Status**: 🚧 In Development (Phase 1 - Proof of Concept)

**Last Updated**: May 7, 2026

**Next Milestone**: Complete basic receipt upload and processing functionality

---

## Contact

**Project Maintainer**: [Your Name]

**Project Link**: [https://github.com/yourusername/ShoppingTracker](https://github.com/yourusername/ShoppingTracker)

---

Made with ❤️ as a learning project for exploring web development and AI integration.
