FROM python:3
RUN apt update
RUN apt install -y at
RUN git clone https://github.com/dbmage/dbmage-bot.git --single-branch --branch=update /app/
RUN git clone https://github.com/dbmage/at.git /tmp/at &&\
cp -r /tmp/at /usr/lib/python3.7/
cp /app/requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt &&\
rm /tmp/requirements.txt
CMD [ "python", "/app/dbmageBot.py" ]
