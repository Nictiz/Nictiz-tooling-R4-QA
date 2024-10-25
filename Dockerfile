FROM alpine:3.18
RUN apk upgrade
RUN apk add bash
RUN apk add wget
RUN apk add openjdk11-jre-headless
RUN apk add git
RUN apk add python3 py3-pip py3-yaml py3-requests py3-aiohttp
RUN pip3 install jsonpath-python

RUN mkdir /tools
RUN mkdir /input
RUN mkdir /scripts

RUN mkdir tools/validator
RUN wget -nv https://github.com/hapifhir/org.hl7.fhir.core/releases/download/6.4.0/validator_cli.jar -O /tools/validator/validator.jar
RUN java -jar /tools/validator/validator.jar -version 4.0 -ig nictiz.fhir.nl.r4.profilingguidelines -tx 'n/a' | cat

RUN git clone -b master --depth 1 https://github.com/pieter-edelman-nictiz/hl7-fhir-validator-action /tools/hl7-fhir-validator-action

COPY entrypoint.py /entrypoint.py
COPY server /server

RUN mkdir builtin_scripts
COPY --chmod=755 builtin_scripts/* /builtin_scripts
RUN apk add dos2unix
RUN dos2unix /builtin_scripts/*

ENTRYPOINT ["python3", "/entrypoint.py"]
