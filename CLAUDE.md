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

### Version 1 - Proof of Concept (Current Target)
- Local web application (no deployment)
- No authentication/authorization
- File-based database (local storage)
- Focus: Get the core functionality working

### Version 2 - Deployable Version (Future)
- Deployable web application
- User/password authentication
- Relational database (e.g., PostgreSQL/MySQL)

## Technology Stack

Based on the .gitignore, this will be a **Python** project. Common frameworks for the proof of concept:
- **Web Framework**: Flask or FastAPI (lightweight, beginner-friendly)
- **LLM Integration**: OpenAI API, Anthropic Claude API, or similar
- **Database**: JSON files or SQLite for V1, migrate to PostgreSQL/MySQL for V2
- **Frontend**: HTML/CSS/JavaScript (or a simple template engine like Jinja2)

## Development Guidelines

### For Beginners
- **Explain your code**: Add comments explaining non-obvious logic
- **Use simple patterns first**: Don't over-engineer; prefer straightforward solutions
- **Break down complex tasks**: Split large features into smaller, testable pieces
- **Educational focus**: When suggesting code, explain *why* you're doing it that way

### Project Structure Recommendations
Since no code exists yet, consider this structure:
```
ShoppingTracker/
├── app/                    # Application code
│   ├── main.py            # Entry point
│   ├── routes.py          # Web routes/endpoints
│   ├── llm_service.py     # LLM integration
│   └── database.py        # Database operations
├── static/                # CSS, JavaScript, images
├── templates/             # HTML templates
├── data/                  # Local database files (V1)
├── tests/                 # Test files
├── requirements.txt       # Python dependencies
└── Specification/         # Project documentation

```

### Key Implementation Notes

1. **Image Processing**: You'll need to handle file uploads and potentially convert images to formats the LLM accepts
2. **LLM Prompt Engineering**: Design prompts to reliably extract structured data (item names, quantities, prices) from receipt images
3. **Data Storage (V1)**: Use JSON files or SQLite - easy to set up and sufficient for local testing
4. **Error Handling**: Receipts can be unclear, handle cases where LLM can't extract data

## Specification Location

Full project requirements: `Specification/ProblemStatement.md`

## Common Commands (To Be Added)

Once dependencies are set up, update this section with:
- How to install dependencies: `pip install -r requirements.txt`
- How to run the application: `python app/main.py` or `flask run`
- How to run tests: `pytest` or `python -m unittest`

## Notes for AI Assistance

- This is a **learning project** - prioritize clarity over cleverness
- The developer is **not experienced** - provide context and explanations
- Start simple for V1, don't jump to V2 features prematurely
- Focus on getting a working prototype before optimization
