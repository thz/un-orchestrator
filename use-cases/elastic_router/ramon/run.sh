#!/bin/bash
./ratemon_client.py -k /keys/ericsson-key.json rate_monitoring ericsson > /dev/null &


./ratemon/run_monitoring -b 9999 
