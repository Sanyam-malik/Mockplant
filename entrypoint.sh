#!/bin/bash

# Run the configuration script
nohup python /app/mockplant_http.py &

mkdir -p /app/logs

touch /app/logs/mockplant.log

# Keep the container running
tail -f /app/logs/mockplant.log

