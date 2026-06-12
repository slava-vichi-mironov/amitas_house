#!/usr/bin/env bash
# Rebuild the model and push to GitHub — Pages deploys automatically via Actions.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Rebuilding house.json =="
npm run build

if ! command -v gh &>/dev/null; then
  echo ""
  echo "Install GitHub CLI:  brew install gh  &&  gh auth login"
  exit 1
fi

if ! git remote get-url origin &>/dev/null 2>&1; then
  echo ""
  read -r -p "GitHub repo name [amitas_house]: " REPO
  REPO="${REPO:-amitas_house}"
  read -r -p "Public repo? (required for free Pages on personal account) [y/N]: " PUBLIC
  if [[ "${PUBLIC,,}" == "y" ]]; then
    gh repo create "$REPO" --public --source=. --remote=origin
  else
    gh repo create "$REPO" --private --source=. --remote=origin
    echo "Note: GitHub Pages on private repos needs GitHub Pro, or use Netlify Drop instead."
  fi
  echo ""
  echo "After first push: repo Settings → Pages → Source: GitHub Actions"
fi

# Never stage the private PDF (also in .gitignore)
git add -A
git reset -- plans/house_plans.pdf 2>/dev/null || true
git reset -- plans/pages plans/crops 2>/dev/null || true
git reset -- plans/extracted_*.json 2>/dev/null || true
git reset -- node_modules .venv 2>/dev/null || true

if git diff --cached --quiet; then
  echo "Nothing to commit."
else
  git commit -m "Deploy viewer"
fi

BRANCH="$(git branch --show-current 2>/dev/null || echo main)"
if ! git rev-parse --verify "$BRANCH" &>/dev/null; then
  git branch -M main
  BRANCH=main
fi

git push -u origin "$BRANCH"

echo ""
echo "✓ Pushed. Deploy workflow: pages.yml"
echo "  Watch:  gh run list --workflow=pages.yml"
echo "  URL:    Settings → Pages  (after workflow succeeds)"
echo "          https://<user>.github.io/<repo>/"
