FROM      ubuntu
MAINTAINER iMinds

RUN apt-get update
RUN apt-get install -y openvswitch-switch openvswitch-common


ADD start.sh start.sh
RUN chmod +x start.sh

CMD ./start.sh
