FROM python:3

WORKDIR /opt/web-53

COPY server.py setup.py config.yml ./

RUN pip install --no-cache-dir --user .

EXPOSE 8080

CMD [ "python", "./server.py" ]