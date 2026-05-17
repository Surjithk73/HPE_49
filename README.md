# QueryCraft

> Natural Language to SQL Performance Report Generator for HPE NonStop Systems

## Overview

QueryCraft allows analysts to query HPE NonStop server performance data using plain English. The system interprets queries, generates SQL, executes against PostgreSQL, and returns structured reports.

**Database Schema:** `macht413` — 9 tables (cpu, disc, dfile, dopen, file, ossns, proc, tmf, udef)  
**Data Source:** Real HPE NonStop measurement data  
**Stack:** FastAPI + React + PostgreSQL + Gemini API

## Quick Start

### Prerequisites

- PostgreSQL (latest stable)
- Python 3.10+
- Node.js 18+ (LTS)
- Gemini API key

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
uvicorn main:app --reload --port 8000
```

**⚠️ Important:** After setting up the database, run the OSSNS table fix to enable aggregate functions on numeric columns. See `OSSNS_FIX_INSTRUCTIONS.md` for details.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`  
Backend: `http://localhost:8000`  
API Docs: `http://localhost:8000/docs`

## Project Structure

See `Project_Overview.md` for detailed architecture and `plan.md` for implementation phases.
