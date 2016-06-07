#! /bin/sh

name=${1:-ramon}
interface=${2:-veth0}
ramon_port=${3:-55555}
config_port=${4:-54736}

NO_HELLO=--no_hello             # use this when debugging
#NO_HELLO=''                     # use this in "production"

RATEMON_CLIENT=./ratemon_client.py
## Temporary path to RAMON
#RAMON_PATH=../../../../aggregator/ramon/ramon_svn/run_monitor.py
## Use this path when the submodule for RAMON is OK.
RAMON_PATH=./ramon_src/run_monitor.py

DOUBLEDECKER_KEYS=/etc/doubledecker/public-keys.json

RAMON_SAMPLE_RATE=20
RAMON_ESTIMATION_INTERVAL=1
RAMON_LINK_SPEED=10
RAMON_METER_INTERVAL=1
RAMON_ALARM_TRIGGER=90
RAMON_CUTOFF=90

xterm -T ${name}_dd -e "${RATEMON_CLIENT} -k ${DOUBLEDECKER_KEYS} ${name} a ${NO_HELLO} -p ${ramon_port} -q ${config_port} --ramon_path ${RAMON_PATH} --ramon_args -i ${interface} -s ${RAMON_SAMPLE_RATE} -e ${RAMON_ESTIMATION_INTERVAL} -k ${RAMON_LINK_SPEED} -m ${RAMON_METER_INTERVAL} -a ${RAMON_ALARM_TRIGGER} -o ${RAMON_CUTOFF} -q ${config_port}; read" &
