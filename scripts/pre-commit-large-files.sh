#!/bin/bash
# Pre-commit hook: Prevent committing files larger than 50MB
# Install: cp .pre-commit-hooks/large-file-check.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

maxsize=$((50 * 1024 * 1024))  # 50MB in bytes

for file in $(git diff --cached --name-only); do
    if [ -f "$file" ]; then
        size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null)
        if [ -n "$size" ] && [ "$size" -gt "$maxsize" ]; then
            mb_size=$((size / 1024 / 1024))
            echo "ERROR: $file is larger than 50MB (${mb_size}MB)"
            echo "Add to .gitignore or use Git LFS"
            exit 1
        fi
    fi
done

exit 0
