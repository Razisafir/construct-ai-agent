#!/bin/bash
# Run all Python tests with coverage reporting.
#
# Usage:
#   cd /mnt/agents/output/construct
#   ./tests/python/run_tests.sh
#   ./tests/python/run_tests.sh -v          # verbose mode
#   ./tests/python/run_tests.sh -k memory   # filter tests by keyword
#   ./tests/python/run_tests.sh --no-cov    # skip coverage

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TESTS_DIR="${SCRIPT_DIR}"
COVERAGE_DIR="${PROJECT_ROOT}/.coverage-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COVERAGE_FILE="${COVERAGE_DIR}/coverage_${TIMESTAMP}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Parse arguments
VERBOSE=""
KEYWORD=""
SKIP_COV=false
PYTEST_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -k|--keyword)
            KEYWORD="-k $2"
            shift 2
            ;;
        --no-cov)
            SKIP_COV=true
            shift
            ;;
        *)
            PYTEST_ARGS="${PYTEST_ARGS} $1"
            shift
            ;;
    esac
done

# Create coverage directory
mkdir -p "${COVERAGE_DIR}"

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  Construct Python Test Suite${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo -e "${BLUE}Project root:${NC} ${PROJECT_ROOT}"
echo -e "${BLUE}Test dir:${NC}     ${TESTS_DIR}"
echo -e "${BLUE}Coverage:${NC}     ${SKIP_COV && echo "skipped" || echo "${COVERAGE_FILE}"}"
echo ""

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import pytest" 2>/dev/null || {
    echo -e "${RED}pytest not installed. Install with: pip install pytest${NC}"
    exit 1
}

if [[ "${SKIP_COV}" == false ]]; then
    python3 -c "import pytest_cov" 2>/dev/null || {
        echo -e "${YELLOW}pytest-cov not installed. Coverage will be skipped.${NC}"
        SKIP_COV=true
    }
fi
echo -e "${GREEN}Dependencies OK${NC}"
echo ""

# Build pytest command
PYTEST_CMD="python3 -m pytest"
PYTEST_CMD="${PYTEST_CMD} ${TESTS_DIR}"
PYTEST_CMD="${PYTEST_CMD} ${VERBOSE}"
PYTEST_CMD="${PYTEST_CMD} ${KEYWORD}"

if [[ "${SKIP_COV}" == false ]]; then
    PYTEST_CMD="${PYTEST_CMD} --cov=src --cov-report=term-missing"
    PYTEST_CMD="${PYTEST_CMD} --cov-report=html:${COVERAGE_FILE}_html"
    PYTEST_CMD="${PYTEST_CMD} --cov-report=xml:${COVERAGE_FILE}.xml"
fi

PYTEST_CMD="${PYTEST_CMD} --tb=short"
PYTEST_CMD="${PYTEST_CMD} -ra"
PYTEST_CMD="${PYTEST_CMD} ${PYTEST_ARGS}"

# Run tests
echo -e "${BOLD}Running tests...${NC}"
echo -e "${BLUE}Command:${NC} ${PYTEST_CMD}"
echo ""

set +e
${PYTEST_CMD}
EXIT_CODE=$?
set -e

echo ""
echo -e "${BOLD}========================================${NC}"

if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}Some tests failed (exit code: ${EXIT_CODE})${NC}"
fi

if [[ "${SKIP_COV}" == false ]]; then
    echo ""
    echo -e "${BLUE}Coverage reports:${NC}"
    echo "  HTML: ${COVERAGE_FILE}_html/index.html"
    echo "  XML:  ${COVERAGE_FILE}.xml"
fi

echo -e "${BOLD}========================================${NC}"

exit ${EXIT_CODE}
