# V2 Roadmap — Shopping Tracker

V2 transforms the local proof-of-concept into a deployable, multi-user web application.
This document is the single source of truth for V2 scope — supersedes any V2 notes
scattered in CLAUDE.md, ProjectSetup.md, or ProblemStatement.md.

---

## Goal

Deploy Shopping Tracker on an external server so multiple users can each track their own
shopping independently, with secure login and a proper relational database.

---

## V2 Feature Scope

### Authentication
- Google OAuth login (Flask-Dance + Google Cloud Console)
- Each user signs in with their Google account
- Logged-out visitors are redirected to the login page
- Sign in / Sign out button in navigation

### Per-user data isolation
- Every receipt stores the owner's Google email (`user_email` field)
- History page shows only the logged-in user's receipts
- One user cannot see or delete another user's receipts

### Relational database
- Migrate from JSON files to PostgreSQL (hosted on Azure)
- Database abstraction layer already supports swapping implementations (one-line change)
- Migration script needed: JSON → PostgreSQL

### Deployment
- Target platform: Azure (App Service or similar)
- HTTPS required (Google OAuth blocks non-HTTPS for non-localhost URIs)
- Environment variables managed via Azure configuration, not `.env` files
- Linux server (development has been Windows)

### Edit / Delete
- Edit extracted receipt data before or after saving
- Delete with confirmation (soft delete already implemented in V1)

### Search and filters
- Filter receipts by store name, date range, category
- Full-text search across item names

### Analytics dashboard
- Spending by category (chart)
- Monthly spending trend
- Top stores by spend

### Export
- Export receipt history to CSV

---

## Deferred from V1 (already scoped out)

These were explicitly excluded from V1 and belong in V2:

- User authentication of any kind
- Multi-user support
- Cloud / server deployment
- Relational database
- Edit functionality
- Advanced search and filtering
- Statistics and charts
- Data export

---

## V2 Prerequisites (must be done before V2 starts)

1. V1 fully working and stable (all core features passing tests)
2. Google Cloud project created with OAuth credentials
3. Azure subscription active
4. PostgreSQL schema designed and migration script tested locally

---

## Out of scope (not planned)

- Mobile app (native iOS/Android)
- Receipt image storage / preview
- Multi-currency conversion / exchange rates
- Shared receipts between users
- Barcode / QR code scanning
