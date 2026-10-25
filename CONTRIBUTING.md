# Contributing to Nabta

A few simple rules so five people can work in the same repository without breaking each other's work.

## 1. Work in your own folder

Each member owns a folder (see the table in the main README). Only edit someone else's folder after telling them.

## 2. Never push directly to `main`

1. Create a branch for your task:
   ```bash
   git checkout main
   git pull
   git checkout -b <area>/<short-task-name>
   ```
   Examples: `hardware/sensor-test`, `ai/safety-rules`, `dashboard/home-screen`, `docs/plant-research`
2. Commit your work on that branch.
3. Push it and open a **Pull Request** to `main`.
4. Ask one teammate to review, then merge.

## 3. Commit messages

Start with the area, then say what you did:

```
hardware: add soil moisture sensor test
ai: define assistant safety rules
docs: add meeting notes for week 2
dashboard: sketch chat screen
```

## 4. Tasks

Every task is a GitHub **Issue**, using the "Task" template. Assign it to yourself, and close it from your Pull Request by writing `Closes #<issue number>`.

## 5. Never commit

- Passwords, API keys or Wi-Fi credentials (use a `.env` file, it's ignored by git)
- Large model files (`.gguf`, `.bin`) – share download links instead
- Personal or temporary files
