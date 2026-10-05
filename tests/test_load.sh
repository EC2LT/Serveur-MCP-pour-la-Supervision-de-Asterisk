#!/bin/bash
# Test de charge SIPp progressif : 10 → 50 canaux

SIPP_TARGET="${1:-127.0.0.1:5060}"
SCENARIO="$(dirname "$0")/sipp_scenario.xml"

echo "=============================================="
echo " Test de charge SIPp vers $SIPP_TARGET"
echo "=============================================="

for CONCURRENT in 10 20 30 40 50; do
    echo ""
    echo ">>> Test avec $CONCURRENT canaux simultanés"

    sipp -sf "$SCENARIO" \
         -d 8000 \
         -r $((CONCURRENT / 2)) \
         -rp 1000 \
         -l "$CONCURRENT" \
         -m $((CONCURRENT * 3)) \
         -trace_stat \
         -trace_err \
         -nostdin \
         "$SIPP_TARGET"

    echo ">>> Résultats $CONCURRENT canaux :"
    ls -t sipp_*_scenario.csv 2>/dev/null | head -1 | xargs -I{} python3 "$(dirname "$0")/analyze_sipp.py" {} 2>/dev/null

    sleep 5
done

echo ""
echo "=============================================="
echo " Tests terminés."
echo "=============================================="
