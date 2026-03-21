# GitHub Code Push Guide

This guide outlines the standard process for committing and pushing your code changes to the GitHub repository: `git@github.com:DurveshCoder/AMS-AI-System.git`.

## 1. Check Git Status
Before committing, it's always a good practice to review which files have been modified or are currently untracked.
```bash
git status
```

## 2. Stage Your Changes
Stage the files you want to include in your next commit.

**To stage all changes (modified and new files):**
```bash
git add .
```

**To stage a specific file:**
```bash
git add path/to/your/file.ts
```

## 3. Commit Your Changes
Create a commit with a descriptive message explaining the changes you made.
```bash
git commit -m "Your descriptive commit message here"
```
*Example: `git commit -m "feat: implement bulk delete for assets"`*

## 4. Push to GitHub
Finally, push your committed changes to the remote repository.
```bash
git push origin main
```
*(Assuming you are working on the `main` branch. If working on a different branch, replace `main` with your branch name).*

## Submitting a Pull Request (Optional)
If you are working on a feature branch instead of `main`, you will typically open a Pull Request (PR) on GitHub after pushing to review before merging into `main`.

## Common Setup & Troubleshooting

- **Check Remote Repository:** To verify where your code is being pushed.
  ```bash
  git remote -v
  ```
- **Merge Conflicts:** If there are new commits in the remote repository that you don't have locally, your push will be rejected. 
  ```bash
  git pull origin main
  # (resolve any conflicts in your code editor)
  git add .
  git commit -m "Merge remote changes and resolve conflicts"
  git push origin main
  ```
- **Authentication Issues:** Since you are using SSH, ensure your SSH key is added to your GitHub account and your SSH agent is running if you encounter permission denied errors.
