FROM alpine:3.12
RUN apk add git
RUN mkdir /server; \
		git clone https://github.com/Sareff/skill53.git /server
EXPOSE 8080
CMD cd /server; ./web-53