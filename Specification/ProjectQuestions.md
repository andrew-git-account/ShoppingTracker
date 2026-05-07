# Project Setup Questions

This document contains questions that need to be answered before starting development. Your answers will guide the technical decisions and implementation approach.

## 1. Project Goals & Priorities

### Learning Objectives
- [ ] **What do you want to learn most from this project?**
  - Web development fundamentals
  - Working with APIs (especially AI/LLM)
  - Database design and management
  - Full-stack development
  - Python programming
  - All of the above
Answer: All of the above with the emphasis on AI/LLM 

- [ ] **How much time can you dedicate to this project?**
  - A few hours per week (slow, steady progress)
  - Several hours per week (moderate pace)
  - Full-time learning (intensive)
Answer: a few hours a day 

- [ ] **What's your priority for Version 1?**
  - Get something working quickly (minimal features)
  - Build it properly from the start (more time, better structure)
  - Learn as much as possible (focus on understanding)
Answer: get something quickly (minmal features) and gradually extend it 

## 2. Technical Stack Decisions

### Web Framework
- [x] **Which Python web framework do you want to use?**
  - **Flask**: Simple, lightweight, great for beginners, lots of tutorials
    - Pros: Easy to learn, flexible, minimal boilerplate
    - Cons: Need to add features manually
  - **FastAPI**: Modern, fast, automatic API docs, growing popularity
    - Pros: Built-in validation, modern Python features, great for APIs
    - Cons: Slightly steeper learning curve
  - **Not sure**: Want recommendation based on learning goals
Answer: Flask 

### LLM Provider
- [ ] **Which AI provider do you want to use for receipt processing?**
  - **OpenAI (GPT-4 Vision)**
    - Pros: Excellent at OCR/image analysis, well-documented, popular
    - Cons: Costs money per API call (~$0.01-0.03 per receipt)
    - API Key required from: https://platform.openai.com/
  
  - **Anthropic (Claude with Vision)**
    - Pros: Strong vision capabilities, detailed responses, good pricing
    - Cons: Newer, slightly less documentation than OpenAI
    - API Key required from: https://console.anthropic.com/
  
  - **Google (Gemini Vision)**
    - Pros: Good performance, competitive pricing
    - Cons: Less specialized in receipt processing
  
  - **Not sure**: Want recommendation
Answer: Anthropic Claude (I can handle API key) 

- [ ] **Do you have an API key already?**
  - Yes, OpenAI
  - Yes, Anthropic
  - Yes, other provider: _______________
  - No, need to create account and get one
Answer: Yes

- [ ] **Are you comfortable with API costs?**
  - Yes, I have a budget for API calls
  - Want to minimize costs (we'll optimize prompts, add caching)
  - Want free/cheap alternatives (we can look at open-source models)
  - Not sure about costs (need more information)
Answer: Yes

### Database Choice (Version 1)
- [ ] **Which database approach for V1?**
  - **SQLite**: Real database, SQL practice, easy migration to V2
    - Pros: Professional, portable, no setup needed
    - Cons: Need to learn SQL basics
  
  - **JSON files**: Simple text files, easy to understand
    - Pros: No setup, easy to debug, human-readable
    - Cons: Not scalable, harder to migrate later
  
  - **Not sure**: Want recommendation
Answer: let's start with JSON files 

### Frontend Approach
- [ ] **How much do you want to focus on the user interface?**
  - **Minimal**: Very basic HTML forms, focus on backend functionality
  - **Simple but clean**: Basic styling with CSS, functional design
  - **Modern look**: Use CSS framework (Bootstrap/Tailwind), nice design
  - **Not sure**: Want recommendation
Answer: Simple but clean 

- [ ] **Do you want to use JavaScript for interactivity?**
  - Yes, want dynamic page updates (AJAX, no page reloads)
  - No, simple page reloads are fine (easier to start)
  - Not sure yet
Answer: No for the beginning

## 3. Feature Scope for Version 1

### Core Features (Mandatory)
These are essential for the proof of concept:
- [x] Upload receipt photo
- [x] Extract data using LLM
- [x] Store data in database
- [x] Display shopping history

### Optional Features for V1
Which of these would you like to include in Version 1?

- [ ] **Edit extracted data before saving**
  - Good if LLM makes mistakes
  - Adds complexity to UI
Answer: no for the beginning

- [ ] **Delete transactions**
  - Useful for mistakes
  - Need delete confirmation
Answer: no for the beginning

- [ ] **Search/filter shopping history**
  - By date range
  - By store name
  - By amount
  - By item name
Answer: no for the beginning

- [ ] **Basic statistics**
  - Total spent this week/month
  - Number of shopping trips
  - Average spending per trip
Answer: no for the beginning

- [ ] **Export data**
  - Download as CSV
  - Download as PDF report
Answer: no for the beginning

- [ ] **Multiple receipt images per transaction**
  - Upload front and back
  - Multiple pages
Answer: no for the beginning - one pager 

- [ ] **Receipt image preview**
  - Show uploaded image alongside extracted data
  - Store images for later reference
Answer: no for the beginning

### Future Features (Defer to V2)
These are explicitly for Version 2:
- User authentication
- Multi-user support
- Cloud deployment
- Advanced analytics
- Mobile app

## 4. Development Environment

### Operating System
- [ ] **What OS are you developing on?**
  - Windows
  - macOS
  - Linux (which distribution: _______________)
Answer: version 1 for Windows, version 2 for Linux 

### Code Editor/IDE
- [ ] **Which editor do you prefer?**
  - Visual Studio Code (recommended for beginners)
  - PyCharm
  - Sublime Text
  - Other: _______________
  - Not sure / need recommendation
Answer: Notepad++

### Python Version
- [x] **Which Python version do you have installed?**
  - Python 3.8
  - Python 3.9
  - Python 3.10
  - Python 3.11
  - Python 3.12
  - Python 3.13
  - Not sure (need to check: `python --version`)
  - Not installed yet
Answer: Python 3.13.0 

### Version Control Experience
- [ ] **How comfortable are you with Git?**
  - Very comfortable (use it regularly)
  - Basic knowledge (can commit and push)
  - Beginner (need guidance)
  - Never used it (need tutorial)
Answer: basic knowledge 

## 5. Data & Privacy

### Receipt Data
- [ ] **What information do you want to extract from receipts?**
  - **Required**: Item names and prices
  - Store name
  - Purchase date/time
  - Payment method
  - Category of items (food, household, etc.)
  - Tax amount
  - Discounts/coupons
Answer: store name, Purchase date, Tax amount, Discounts/coupons

### Data Storage
- [ ] **How long do you want to keep receipt data?**
  - Forever (no automatic deletion)
  - Set retention period (e.g., 2 years)
  - Manual deletion only
Answer: Forever 

- [ ] **Do you want to store actual receipt images?**
  - Yes, keep images for reference
    - Pros: Can review later if extraction was wrong
    - Cons: Takes disk space
  - No, delete after processing
    - Pros: Saves space
    - Cons: Can't verify data later
Answer: No, delete after processing

## 6. Budget & Resources

### API Costs
- [ ] **What's your monthly budget for API calls?**
  - $0 (free tier only)
  - $5-10/month (occasional use, ~100-300 receipts)
  - $10-20/month (regular use, ~300-600 receipts)
  - $20+/month (frequent use)
  - No specific budget
Answer: regular use

### Development Time
- [ ] **When do you want Version 1 completed?**
  - 1-2 weeks (aggressive timeline)
  - 1 month (comfortable pace)
  - 2-3 months (relaxed, thorough learning)
  - No deadline (work at my own pace)
Answer: no deadline 

## 7. Testing & Quality

### Testing Approach
- [ ] **How important is automated testing to you?**
  - Very important (write tests from the start)
  - Somewhat important (add basic tests)
  - Low priority (manual testing is fine for V1)
  - Want to learn testing (include it as learning objective)
Answer: very important 

### Code Quality
- [ ] **Do you want to use code quality tools?**
  - Yes, use linters (pylint, flake8) from the start
  - Yes, but add them later
  - No, focus on functionality first
  - Not sure what these are
Answer: Yes, but add them later

## 8. Documentation Preferences

### Code Comments
- [ ] **How much documentation do you want in the code?**
  - Heavy commenting (explain everything for learning)
  - Moderate (comment complex logic only)
  - Minimal (clean code should be self-documenting)
Answer: Heavy commenting 

### Learning Documentation
- [ ] **Would you like explanations of design decisions?**
  - Yes, explain WHY we do things a certain way
  - Just show HOW to do things
  - Minimal explanation, I'll research on my own
Answer: Yes

## 9. Deployment Plans (Future)

Even though this is for V2, it helps to think ahead:

- [ ] **Where might you deploy Version 2?**
  - Heroku (easy, beginner-friendly)
  - AWS (more complex, industry standard)
  - Azure (Microsoft ecosystem)
  - Google Cloud Platform
  - DigitalOcean (simple VPS)
  - Railway/Render (modern, simple)
  - Not sure yet / want recommendations
Answer: Azure

## 10. Personal Preferences

### Work Style
- [ ] **How do you prefer to work?**
  - Build everything from scratch (maximum learning)
  - Use libraries/frameworks when available (faster progress)
  - Balance of both
Answer: Balance of both

### Error Handling
- [ ] **When things go wrong, how should the app behave?**
  - Show detailed error messages (good for learning/debugging)
  - Show user-friendly messages (better UX)
  - Log errors to file for later review
Answer: Show user-friendly messages 

### Project Structure
- [ ] **Do you prefer?**
  - Start simple, refactor later as you learn
  - Set up proper structure from the beginning
  - Not sure (want guidance)
Answer: Start simple, refactor later as you learn

---

## Summary Checklist

Before proceeding to development, ensure you have:

- [x] Chosen a web framework (Flask or FastAPI) - Flask ✓
- [x] Selected and obtained API key for LLM provider - Anthropic Claude ✓
- [x] Decided on database approach (SQLite or JSON) - JSON files ✓
- [x] Determined V1 feature scope - Core features only ✓
- [x] Set up development environment (Python, editor, Git) - Python 3.13.0, Notepad++, Git ✓
- [x] Understood API cost implications - $10-20/month budget ✓
- [x] Defined what data to extract from receipts - Items, prices, store, date, tax, discounts ✓
- [x] Established timeline expectations - No deadline, work at own pace ✓

---

## Next Steps

Once these questions are answered:

1. Create `requirements.txt` with necessary dependencies
2. Set up project structure (folders, files)
3. Create `.env.example` template for configuration
4. Build first feature: file upload endpoint
5. Integrate LLM API for receipt processing
6. Implement database layer
7. Create basic UI
8. Test with real receipts
9. Iterate and improve

---

**Note**: It's okay to change your mind later! These answers help us get started, but we can adjust as you learn and discover what works best for you.
