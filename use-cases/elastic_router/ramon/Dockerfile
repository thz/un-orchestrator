FROM debian:testing
MAINTAINER Bertrand Pechenot berpec@acreo.se
RUN apt-get update --fix-missing
# RUN DEBIAN_FRONTEND=noninteractive apt-get install -yq apt-utils wget build-essential libtool git
# RUN DEBIAN_FRONTEND=noninteractive apt-get install -yq automake pkg-config libjson0-dev libzmq3-dev
RUN DEBIAN_FRONTEND=noninteractive apt-get install -yq python \
                    python3 \
                    python-scipy \
                    python3-nacl \
                    python3-zmq \
                    python3-setuptools \
                    python3-future \
                    net-tools \
                    python-pip \
                    wget

# Broker default port 
EXPOSE 5555 

# TODO: write a run.sh script that handles ENV variables properly
RUN mkdir /ramon
ADD ./ratemon_client.py /ramon/
ADD ./ramon_src/* /ramon/
WORKDIR /
RUN wget https://github.com/Acreo/DoubleDecker-py/archive/master.tar.gz -O dd.tar.gz
RUN tar xzf dd.tar.gz
RUN rm dd.tar.gz
WORKDIR /DoubleDecker-py-master/
RUN python3 setup.py build
RUN python3 setup.py install
RUN pip install sh

RUN DEBIAN_FRONTEND=noninteractive apt-get autoremove -yq
RUN DEBIAN_FRONTEND=noninteractive apt-get autoclean -yq
#CMD ./run.sh

# [PD] 2016-06-07, added environment variables and new CMD
ENV name=ramon
ENV interface=veth0
ENV ramon_port=55555
ENV config_port=54736
ENV RAMON_PATH=/ramon/run_monitor.py
ENV DOUBLEDECKER_KEYS=/keys/public-keys.json
ENV RAMON_SAMPLE_RATE=20
# samples/second; 20 means sample every 50ms
ENV RAMON_ESTIMATION_INTERVAL=1
# estimate the distribution every 1 second
ENV RAMON_LINK_SPEED=10
# link speed of the interface monitored,
# in Mbits/second
ENV RAMON_METER_INTERVAL=1
# report (to ratemon_client) every 1 second
ENV RAMON_ALARM_TRIGGER=90
# over this risk (in percent) the monitor will
                           # trigger an overload alarm
ENV RAMON_CUTOFF=90
# use this percentage as a cutoff when calculating
# the overload risk
WORKDIR /ramon/
CMD ./ratemon_client.py -k ${DOUBLEDECKER_KEYS} \
            ${name} \
            ${NO_HELLO} \
            -p ${ramon_port} \
            -q ${config_port} \
            --ramon_path ${RAMON_PATH} \
            --ramon_args -i ${interface} \
            -s ${RAMON_SAMPLE_RATE} \
            -e ${RAMON_ESTIMATION_INTERVAL} \
            -k ${RAMON_LINK_SPEED} \
            -m ${RAMON_METER_INTERVAL} \
            -a ${RAMON_ALARM_TRIGGER} \
            -o ${RAMON_CUTOFF} \
            -q ${config_port}
