#! /bin/bash

#This gives time to the UN to configure the network namespace of the container
sleep 3


echo "Ubuntu started"
echo "start ovs"
service openvswitch-switch start

echo "add controller interface 10.0.10.2/24 on eth0"
ifconfig eth0 0
ip addr add 10.0.10.4/24 dev eth0

#echo "setup ovs bridge"
ovs-vsctl add-br $NAME
ovs-vsctl set bridge $NAME datapath_type=netdev
ovs-vsctl set bridge $NAME protocols=OpenFlow10,OpenFlow12,OpenFlow13
ovs-vsctl set-fail-mode $NAME secure
ovs-vsctl set bridge $NAME other_config:disable-in-band=true

ovs-vsctl add-port $NAME ${NAME}_eth0
ovs-vsctl add-port $NAME ${NAME}_eth1
ovs-vsctl add-port $NAME ${NAME}_eth2
ovs-vsctl add-port $NAME ${NAME}_eth3

ovs-vsctl set-controller $NAME tcp:10.0.10.100:6633

# keep container running
while true
do
	sleep 1
done

