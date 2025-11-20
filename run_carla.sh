#!/bin/bash

(trap 'kill 0' SIGINT;
~/programs/carla9/CarlaUE4.sh &
sleep 8
python3 recless_drive.py &
wait)