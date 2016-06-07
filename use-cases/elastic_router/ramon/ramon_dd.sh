#! /bin/sh

name=${1:-ramon}
interface=${2:-veth0}
ramon_port=${3:-55555}
config_port=${4:-54736}

NO_HELLO=--no_hello             # use this when debugging
#NO_HELLO=''                     # use this in "production"

RATEMON_CLIENT=./ratemon_client.py
RAMON_PATH=../../../../aggregator/ramon/ramon_svn/run_monitor.py

#xterm -T ${name}_dd -e "${RATEMON_CLIENT} -k /etc/doubledecker/a-keys.json ${name} a -p ${ramon_port} -q ${config_port} --ramon_args -i ${interface} -s 20 -e 1 -k 10 -m 1 -q ${config_port}; read" &

xterm -T ${name}_dd -e "${RATEMON_CLIENT} -k /etc/doubledecker/a-keys.json ${name} a ${NO_HELLO} -p ${ramon_port} -q ${config_port}  --ramon_path ${RAMON_PATH} --ramon_args -i ${interface} -s 20 -e 1 -k 10 -m 1 -a 90 -o 90 -q ${config_port}; read" &
