FROM python:3.11-slim

WORKDIR /app


COPY driver.json .
COPY requirements.txt .
COPY ./uc_intg_epson_pj/ ./uc_intg_epson_pj/

RUN pip install --no-cache-dir -r requirements.txt

ADD . .

ENV UC_DISABLE_MDNS_PUBLISH="false"
ENV UC_MDNS_LOCAL_HOSTNAME=""
ENV UC_INTEGRATION_INTERFACE="0.0.0.0"
ENV UC_INTEGRATION_HTTP_PORT="9099"
ENV UC_CONFIG_HOME="/config"

CMD ["python", "-m", "uc_intg_epson_pj.driver"]