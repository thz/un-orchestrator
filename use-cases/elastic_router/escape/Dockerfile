FROM python:2.7

COPY . /escape-shared
COPY . /er-topo_v1.nffg

RUN useradd -m docker && echo "docker:docker" | chpasswd && adduser docker sudo
USER DOCKER

WORKDIR /escape-shared  
RUN ./install-dep.sh

CMD ./escape.py -s er-sg.nffg
