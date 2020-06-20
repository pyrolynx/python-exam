FROM python:3.6

WORKDIR /opt

ENV PYTHONUNBUFFERED 1

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT ["./entrypoint.sh"]
