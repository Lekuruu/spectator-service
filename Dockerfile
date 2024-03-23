FROM python:3.11-alpine

WORKDIR /spectator-service

# Install python dependencies
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy source code
COPY . .

STOPSIGNAL SIGINT

ENV USERNAME $USERNAME
ENV PASSWORD $PASSWORD
ENV SERVER $SERVER

ENV REDIS_HOST $REDIS_HOST
ENV REDIS_PORT $REDIS_PORT

CMD python3 main.py \
    --redis-host $REDIS_HOST \
    --redis-port $REDIS_PORT \
    --server $SERVER \
    $USERNAME $PASSWORD