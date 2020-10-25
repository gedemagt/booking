FROM python:3.8

WORKDIR /app

COPY . .

RUN pip3 install gunicorn
RUN pip3 install -r requirements.txt

CMD ["gunicorn", "--workers=2", "--bind", "0.0.0.0:8050", "main:fapp"]

