FROM python:3.11-slim


LABEL org.opencontainers.image.authors="Jiepeng Huang <s4735258@student.uq.edu.au>"

LABEL org.opencontainers.image.version="1.0"

LABEL org.opencontainers.image.title="cca4_backend_django:1.0"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
