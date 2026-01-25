#!/bin/bash
#
# X (Twitter) News URL Collector - Manual Run Script
#

# ==============================================================================
# CONFIGURATION - 사용자 환경에 맞춰 수정된 부분
# ==============================================================================

# 프로젝트 디렉토리
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 파이썬 실행 경로 (사용자 시스템의 Python 3.13 반영)
PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"

# 실제 사용 중인 크롬 프로필 경로 (jerry@skygg.xyz 세션 유지용)
CHROME_PROFILE_DIR="/Users/imchaehyeon/Library/Application Support/Google/Chrome/Profile 1"

# 방금 Clone한 깃허브 저장소 경로
GIT_REPO_DIR="/Users/imchaehyeon/Desktop/Vibe Coding/hyperliquid-news-archive"

# 데이터를 저장할 깃허브 내 폴더 구조
GIT_REPO_SUBDIR="data/news"

# ==============================================================================
# SCRIPT LOGIC - 아래는 건드리지 않으셔도 됩니다.
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================================"
echo "  X (Twitter) News URL Collector - Started"
echo "============================================================"
echo ""
echo "Project:  $PROJECT_DIR"
echo "Profile:  $CHROME_PROFILE_DIR"
echo "Git Repo: $GIT_REPO_DIR"
echo ""

# Build the command
# --top-n 100: 초기 수집할 뉴스 개수 (Hyperliquid 필터링 전)
# --final-count 30: 최종 선정할 뉴스 개수 (Hyperliquid 필터링 후)
CMD="$PYTHON -m twitter_news.main"
CMD="$CMD --chrome-profile-dir=\"$CHROME_PROFILE_DIR\""
CMD="$CMD --output-dir=\"$PROJECT_DIR\""
CMD="$CMD --top-n 100"
CMD="$CMD --final-count 30"

# Headless 모드 설정 (인자값이 있으면 반영)
if [[ "$*" == *"--headless"* ]]; then
    CMD="$CMD --headless=true"
    echo "Mode: Headless (background)"
else
    CMD="$CMD --headless=false"
    echo "Mode: Visible browser (Debugging/Login check)"
fi

# Git 옵션 설정
if [ -d "$GIT_REPO_DIR" ]; then
    CMD="$CMD --git=on"
    CMD="$CMD --repo-dir=\"$GIT_REPO_DIR\""
    CMD="$CMD --repo-subdir=\"$GIT_REPO_SUBDIR\""
    echo "Git:  Enabled -> $GIT_REPO_DIR"
else
    echo -e "${RED}Error: Git repository directory not found!${NC}"
    exit 1
fi

echo ""
echo "============================================================"
cd "$PROJECT_DIR"
echo -e "${GREEN}Starting collection and archiving...${NC}"
echo ""

eval $CMD
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Collection completed! Now pushing to GitHub...${NC}"

    # ==============================================================================
    # AUTO-PUSH TO GITHUB
    # ==============================================================================
    cd "$GIT_REPO_DIR"

    TODAY=$(date +%Y-%m-%d)

    # Check if there are changes to commit
    if git diff --quiet && git diff --staged --quiet; then
        UNTRACKED=$(git ls-files --others --exclude-standard "$GIT_REPO_SUBDIR/")
        if [ -z "$UNTRACKED" ]; then
            echo -e "${YELLOW}No new files to push.${NC}"
            exit 0
        fi
    fi

    # Pull latest changes first
    echo "Pulling latest changes..."
    git pull origin main --rebase 2>/dev/null || true

    # Add news files
    echo "Adding files..."
    git add "$GIT_REPO_SUBDIR/"*.txt
    git add "$GIT_REPO_SUBDIR/"*.json 2>/dev/null || true

    # Commit with date message
    COMMIT_MSG="update: news for $TODAY"
    echo "Committing: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"

    # Push to GitHub
    echo "Pushing to GitHub..."
    if git push origin main; then
        echo ""
        echo -e "${GREEN}============================================================${NC}"
        echo -e "${GREEN}✓ Successfully pushed to GitHub!${NC}"
        echo -e "${GREEN}✓ GitHub Action will now trigger website revalidation.${NC}"
        echo -e "${GREEN}============================================================${NC}"
    else
        echo -e "${RED}✗ Failed to push to GitHub. Check your SSH key or credentials.${NC}"
        exit 1
    fi

elif [ $EXIT_CODE -eq 2 ]; then
    echo -e "${RED}✗ Login required in Chrome profile.${NC}"
else
    echo -e "${RED}✗ Process failed with exit code: $EXIT_CODE${NC}"
fi

exit $EXIT_CODE