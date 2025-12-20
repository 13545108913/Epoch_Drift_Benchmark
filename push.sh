#!/bin/bash
REMOTE_BRANCH="main"

# 修正点：去掉 --remotes=，直接使用 origin/main..HEAD
# 这表示：列出所有“在 HEAD 中但不在 origin/main 中”的提交
COMMITS=$(git rev-list --reverse origin/main..HEAD)

if [ -z "$COMMITS" ]; then
    echo "没有检测到需要推送的 Commit (Local 和 Remote 可能已经同步，或者没有新的 Commit)。"
    exit 0
fi

echo "$COMMITS" | while read commit; do
    echo "正在推送 Commit: $commit ..."
    git push origin $commit:$REMOTE_BRANCH
    
    if [ $? -ne 0 ]; then
        echo "❌ 推送失败于 Commit: $commit"
        echo "建议：如果是大文件限制，请针对该 Commit 进行拆分。"
        exit 1
    fi
done
echo "✅ 所有推送已完成！"