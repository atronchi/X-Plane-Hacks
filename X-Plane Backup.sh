#!/bin/bash

echo "Backing up..."

tar -cjvf /tmp/X-Plane\ Backup.tbz2 \
    /Applications/X-Plane\ 10/X-Plane\ Backup.sh \
    /Applications/X-Plane\ 10/Output/preferences \
    /Applications/X-Plane\ 10/Output/FMS\ plans \
    /Applications/X-Plane\ 10/Resources/plugins/PilotEdge \
    /Applications/X-Plane\ 10/Aircraft/General\ Aviation/Cessna\ Skylane\ CTR182 \
    /Applications/X-Plane\ 10/Aircraft/General\ Aviation/Cessna\ Skylane\ CTR182\ mrt \
    /Applications/X-Plane\ 10/Aircraft/General\ Aviation/Cessna\ 172SP \
    /Applications/X-Plane\ 10/Aircraft/General\ Aviation/Cessna\ 172SP\ mrt
    /Applications/X-Plane\ 10/make_flightplan_fms.py

echo "Created backup file at /tmp/X-Plane Backup.tbz2"
