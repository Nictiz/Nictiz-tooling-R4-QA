# 20.04 is the last usable LTS release, as Firely Terminal currently requires a .Net Core version which is not
# supported on Ubuntu 22.04
FROM ubuntu:20.04
RUN apt-get update && apt-get -y upgrade
RUN apt-get -y install wget
RUN apt-get -y install openjdk-11-jre-headless
RUN apt-get -y install git
RUN apt-get -y install python3 python3-pip python3-yaml python3-requests python3-aiohttp
RUN pip3 install jsonpath-python

# Needed for setting tzdata, which is a dependency down the line
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
RUN apt-get -y install tzdata

RUN apt-get -y install mitmproxy

RUN mkdir /tools
RUN mkdir /input
RUN mkdir /scripts

RUN mkdir tools/validator
RUN wget -nv https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar -O /tools/validator/validator.jar
RUN java -jar /tools/validator/validator.jar -version 4.0 -ig nictiz.fhir.nl.r4.profilingguidelines -tx 'n/a' | cat

RUN git clone -b v0.22 --depth 1 https://github.com/pieter-edelman-nictiz/hl7-fhir-validator-action /tools/hl7-fhir-validator-action

COPY entrypoint.py /entrypoint.py
COPY CombinedTX /tools/CombinedTX
COPY server /server
ENTRYPOINT ["python3", "/entrypoint.py"]
