FROM python:3
RUN git clone https://github.com/dbmage/dbmage-bot.git --single-branch --branch=update /app/
ADD requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt &&\
rm /tmp/requirements.txt
CMD [ "python", "/app/dbmageBot.py" ]
