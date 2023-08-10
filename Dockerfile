# 20.04 is the last usable LTS release, as Firely Terminal currently requires a .Net Core version which is not
# supported on Ubuntu 22.04
FROM alpine:3.18
RUN apk upgrade
RUN apk add bash
RUN apk add wget
RUN apk add openjdk11-jre-headless
RUN apk add git
RUN apk add python3 py3-pip py3-yaml py3-requests py3-aiohttp
RUN pip3 install jsonpath-python

# Needed for setting tzdata, which is a dependency down the line
#RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
#RUN apt-get -y install tzdata

#RUN apk add mitmproxy

RUN mkdir /tools
RUN mkdir /input
RUN mkdir /scripts

RUN mkdir tools/validator
RUN wget -nv https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar -O /tools/validator/validator.jar
RUN java -jar /tools/validator/validator.jar -version 4.0 -ig nictiz.fhir.nl.r4.profilingguidelines -tx 'n/a' | cat

RUN git clone -b SuppressErrorsWithUnknownId --depth 1 https://github.com/pieter-edelman-nictiz/hl7-fhir-validator-action /tools/hl7-fhir-validator-action

COPY entrypoint.py /entrypoint.py
#COPY CombinedTX /tools/CombinedTX
COPY server /server
ENTRYPOINT ["python3", "/entrypoint.py"]
