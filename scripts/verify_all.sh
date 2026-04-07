#!/usr/bin/env bash
# Run ALL verification scripts sequentially.
#
# Usage (inside Docker container):
#   bash scripts/verify_all.sh
#
# Or from host:
#   cd /opt/noor && docker compose exec app bash scripts/verify_all.sh

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

total=0
passes=0
failures=0
skipped_scripts=()

run_script() {
    local script="$1"
    local name="$2"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}▶ Running: $name${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    total=$((total + 1))

    if [ ! -f "$script" ]; then
        echo -e "  ${RED}⏭  Script not found: $script${NC}"
        skipped_scripts+=("$name")
        return
    fi

    if python "$script"; then
        passes=$((passes + 1))
        echo -e "${GREEN}▶ $name: PASSED${NC}"
    else
        failures=$((failures + 1))
        echo -e "${RED}▶ $name: FAILED${NC}"
    fi
}

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           TreeJar Integration Verification Suite          ║"
echo "╚═══════════════════════════════════════════════════════════╝"

run_script "scripts/verify_db.py"           "1. Database & Models"
run_script "scripts/verify_crm.py"          "2. Zoho CRM"
run_script "scripts/verify_inventory.py"    "3. Zoho Inventory"
run_script "scripts/verify_wazzup.py"       "4. Wazzup (WhatsApp)"
run_script "scripts/verify_rag_pipeline.py" "5. RAG Pipeline"
run_script "scripts/verify_voice.py"        "6. Voice Recognition"
run_script "scripts/verify_quality.py"      "7. Quality Evaluator"
run_script "scripts/verify_telegram.py"     "8. Telegram Notifications"
run_script "scripts/verify_followups.py"    "9. Follow-ups & Feedback"
run_script "scripts/verify_pdf.py"          "10. PDF / Quotation"
run_script "scripts/verify_api.py"          "11. Health & API Endpoints"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                    VERIFICATION SUMMARY                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo -e "  Total scripts:  $total"
echo -e "  ${GREEN}Passed:         $passes${NC}"
echo -e "  ${RED}Failed:         $failures${NC}"

if [ ${#skipped_scripts[@]} -gt 0 ]; then
    echo -e "  ${YELLOW}Skipped:        ${#skipped_scripts[@]}${NC}"
    for s in "${skipped_scripts[@]}"; do
        echo "    - $s"
    done
fi

echo ""
if [ "$failures" -eq 0 ]; then
    echo -e "${GREEN}✅ All integration checks passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Review output above.${NC}"
    exit 1
fi
