# 1. 파이썬 이미지 (안정적인 3.10 버전)
FROM python:3.10-slim

# 2. 필수 환경 변수
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# 3. MSSQL 및 MySQL 클라이언트 설치를 위한 시스템 패키지
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    build-essential \
    unixodbc-dev \
    libmariadb-dev-compat \
    libmariadb-dev \
    gcc \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 복사
COPY . .

# 6. 포트 설정
EXPOSE 8000

# 7. 실행 (외부 접속 허용을 위해 0.0.0.0으로 실행)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]