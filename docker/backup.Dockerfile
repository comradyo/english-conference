FROM mongo:8

WORKDIR /app

COPY backup/entrypoint.sh /usr/local/bin/mongo-backup-loop.sh
RUN chmod +x /usr/local/bin/mongo-backup-loop.sh

CMD ["mongo-backup-loop.sh"]
