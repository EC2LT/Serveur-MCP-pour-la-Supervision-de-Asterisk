# tests/analyze_sipp.py
import csv
import sys
import glob


def analyze(csv_file: str):
    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Fichier vide.")
        return

    last = rows[-1]
    total = int(last.get("TotalCallCreated", 0) or 0)
    success = int(last.get("SuccessfulCall", 0) or 0)
    failed = int(last.get("FailedCall", 0) or 0)

    print(f"\n{'=' * 50}")
    print(" RAPPORT DE TEST SIPp")
    print(f"{'=' * 50}")
    print(f" Appels créés    : {total}")
    print(f" Appels réussis  : {success}")
    print(f" Appels échoués  : {failed}")
    if total:
        print(f" Taux de succès  : {success / total * 100:.2f}%")
    print(f"{'=' * 50}\n")

    if failed > 0:
        print("⚠️  Des appels ont échoué. Vérifiez :")
        print("   - Charge CPU/RAM d'Asterisk")
        print("   - Latence du pipeline S2S")
        print("   - Logs Asterisk (/var/log/asterisk/full)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        files = sorted(glob.glob("sipp_*_scenario.csv"))
        if files:
            analyze(files[-1])
        else:
            print("Aucun fichier SIPp trouvé.")
