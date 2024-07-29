FROM ubuntu:latest
LABEL authors="flash"

ENTRYPOINT ["top", "-b"]