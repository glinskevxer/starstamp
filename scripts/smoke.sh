#!/usr/bin/env bash
# A day in the shop, through the installed console script.
#
# This lives in the repository rather than in the workflow so that it can be
# run locally and by a test. The workflow used to carry its own copy and it
# drifted: a rule about valve outlets arrived, the chain stopped passing, and
# nothing found out until CI did.
#
# Every line spells the command out rather than going through a helper, so
# that tools/check_workflow.py can walk each one against the real click tree.
# A helper would hide them from it, which is how a chain rots.
#
# Usage: scripts/smoke.sh [working directory]
set -euo pipefail

work="${1:-$(mktemp -d)}"
mkdir -p "$work"
cd "$work"

starstamp --book shop.sqlite3 init
starstamp --book shop.sqlite3 account add WELD1 "Cascade Welding Supply" --opened 2019-04-01
starstamp --book shop.sqlite3 facility add A419 "Wasatch Cylinder Service" --from 2021-05-01 --until 2026-04-30 --methods volumetric,visual
starstamp --book shop.sqlite3 tech add JT7 "Jesse Tovar" --methods volumetric,visual --from 2022-03-01

starstamp --book shop.sqlite3 rig certify WJ-1 "calibrated cylinder" --serial CC-1 --issued 2024-01-15 --until 2029-01-15 --by "Rocky Mountain Calibration"
starstamp --book shop.sqlite3 rig certify WJ-1 gauge --serial PG-1 --issued 2024-01-15 --until 2029-01-15 --by "Rocky Mountain Calibration"
starstamp --book shop.sqlite3 rig certify WJ-1 burette --serial EB-1 --issued 2024-01-15 --until 2029-01-15 --by "Rocky Mountain Calibration"
starstamp --book shop.sqlite3 rig check WJ-1 40.0 40.1 --on 2024-06-12

starstamp --book shop.sqlite3 cylinder register NCI/A4471 --owner WELD1 --spec DOT-3AA2015 --dom 06-98 --service N2 --ree 125.0 --wall 0.220 --valve 580 --on 2024-06-11
starstamp --book shop.sqlite3 lot receive WELD1 NCI/A4471 --on 2024-06-11 --promised 2024-06-28
starstamp --book shop.sqlite3 requal run NCI/A4471 --tech JT7 --system WJ-1 --on 2024-06-12 --applied 3358 --total 110.0 --permanent 2.0
starstamp --book shop.sqlite3 lot ready L2024-0001
starstamp --book shop.sqlite3 lot return L2024-0001 --on 2024-06-13

starstamp --book shop.sqlite3 --today 2024-07-01 fill check NCI/A4471
starstamp --book shop.sqlite3 --today 2024-07-01 fill record NCI/A4471 --by JT7 --to 2015

starstamp --book shop.sqlite3 price set REQUAL_WJ 14.50 --from 2023-01-01
starstamp --book shop.sqlite3 price set HANDLING 5.00 --from 2023-01-01
starstamp --book shop.sqlite3 price set CONDEMN 9.00 --from 2023-01-01
starstamp --book shop.sqlite3 --today 2024-07-01 invoice raise WELD1 --month 2024-06

starstamp --book shop.sqlite3 report packet NCI/A4471
starstamp --book shop.sqlite3 --today 2024-06-12 today
starstamp --book shop.sqlite3 report close --month 2024-06
starstamp --book shop.sqlite3 verify
starstamp --book shop.sqlite3 doctor
starstamp --book shop.sqlite3 about

echo "smoke ok in $work"
