# Contributing to Knowledge Lab

Thanks for your interest! This is a personal project, but contributions are welcome.

## Project Structure

```
apps/       → Client apps (web frontend)
server/     → Backend API + core logic
skills/     → AI skill definitions
standards/  → L0 immutable standards
spec/       → PRD, user research, architecture
docs/       → Screenshots and documentation
scripts/    → Build and utility scripts
tmp/        → Reference projects (gitignored)
```

## Development Setup

```bash
git clone https://github.com/baiwanwan1224-hub/Knowledge-Lab.git
cd Knowledge-Lab
python -m pip install -r requirements.txt
cp .env.example .env   # then edit .env with your API key
```

### Windows
```bash
start.bat
```

### Mac/Linux
```bash
bash start.sh
```

## AI-Assisted Development

This project is built with vibe coding (Claude Code). See `AGENTS.md` for the AI agent context.

## Commit Conventions

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code restructuring
- `chore:` maintenance
