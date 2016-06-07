#FROM python:2.7
FROM ubuntu

ADD ./escape-shared /escape-shared
ADD ./er-sg.nffg   /er-sg.nffg

#RUN useradd -m docker && echo "docker:docker" | chpasswd && adduser docker sudo
#USER DOCKER

WORKDIR /escape-shared  
RUN ./install-dep.sh

CMD ./escape.py -s er-sg.nffg
