FROM python:3
ADD app/* /app/
ADD requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt &&\
rm /tmp/requirements.txt
CMD [ "python", "/app/dbmageBot.py" ]
