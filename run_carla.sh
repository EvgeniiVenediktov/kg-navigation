#!/bin/bash

(trap 'kill 0' SIGINT;
~/programs/carla/CarlaUE4.sh &
sleep 15
python3 add_vehicles.py &
wait)