# KISTI Grid CA 인증서 만료 안내 자동화

## 1. 개요 (Overview)
KISTI Grid CA에서 운영하는 인증서 데이터베이스(`cert`, `csr`)를 매일 조회해 만료 예정 인증서 소유자에게 자동으로 이메일을 발송하는 시스템입니다. 인증서 만료로 인한 서비스 중단을 예방하는 것을 목표로 합니다.

### 주요 기능
- **자동 감지**: 매일 오전 09:00(KST) 스캔
- **다단계 알림**: 만료 14일·7일·3일·1일 전 총 4회 발송
- **영문 안내**: 글로벌 사용자 대응
- **Logging:** - Execution logs: `logs/app.log`
  - Email history (CSV): `logs/email_history.csv` (Timestamp, Recipient, Subject, Days Left)
- **안정성**: 로컬 Postfix + SMTP Relay 기반 발송

## 2. 시스템 환경 (Environment)
| 구분 | 상세 내용 | 비고 |
| --- | --- | --- |
| OS | Linux (Ubuntu/CentOS 등) | Server Host: `ca.gridcenter.or.kr` |
| Language | Python 3.12+ | `venv` 사용 |
| Database | MySQL / MariaDB | `cert`, `csr` 테이블 연동 |
| MTA | Postfix | Localhost 전송 (Relay) |
| Sender | `kisti-grid-ca@kisti.re.kr` | 발신 전용 주소 |

## 3. 디렉터리 구조 (예시 배치: `/opt/cert-notifier`)
```
/opt/cert-notifier/
├─ venv/                 # Python 가상환경
├─ cert_notifier.py      # 메일 발송 스크립트
├─ .env                  # DB 접속 정보 및 환경 변수 (git 추적 제외)
└─ logs/
   ├─ app.log            # 실행/에러 로그
   ├─ cron.log           # 크론 실행 로그
   └─ email_history.csv # Sent Email History
```

## 4. 설치 및 설정
### 4.1 레파지토리 Clone 및 Setup Directory
```bash
sudo mkdir -p /opt/cert-notifier/logs
sudo chown -R $USER:$USER /opt/cert-notifier
git clone <YOUR_REPO_URL> /opt/cert-notifier
```

### 4.2 가상환경 생성 및 패키지 설치
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### `requirements.txt`
```text
pymysql
python-dotenv
```

### 4.3 환경 변수 (`.env`)
`.env`는 코드와 분리해 관리합니다.
```dotenv
DB_HOST=localhost
DB_USER=<입력필요>
DB_PASSWORD=<입력필요>
DB_NAME=<입력필요>
DB_PORT=3306
```

### 4.4 Postfix 설정 (`/etc/postfix/main.cf`)
RFC 5321 준수 및 외부 전송 성공률 향상을 위한 필수 설정 예시입니다.
```ini
# [중요] 호스트네임은 도메인 형식이어야 함
myhostname = ca.gridcenter.or.kr

# 메일 발송 시 도메인 부분 (@뒷부분) 설정
myorigin = kisti.re.kr

# 로컬(서버 내부)에서만 메일을 수신하여 외부로 발송 (Loopback Only)
inet_interfaces = loopback-only
inet_protocols = ipv4

# 목적지 설정
mydestination = $myhostname, localhost, localhost.localdomain, localhost.$mydomain
```

## 5. 실행 방법
### 수동 실행
```bash
pip install -r requirements.txt
source venv/bin/activate
python cert_notifier.py
```

### 크론 스케줄러 (매일 09:00 KST)
`crontab -e`에 아래 라인을 추가합니다.
```cron
00 09 * * * /opt/cert-notifier/venv/bin/python /opt/cert-notifier/cert_notifier.py >> /opt/cert-notifier/logs/cron.log 2>&1
```

## 6. 운영 및 모니터링
- 실행 로그: `tail -f /opt/cert-notifier/logs/app.log`
- 메일 전송 로그: (예) `tail -f /var/log/maillog`
- 메일 발송 내역: `tail -f /opt/cert-notifier/logs/email_history.csv`
- DNS 보안 권장: 
  - PTR(Reverse DNS): `150.183.244.13` ↔ `ca.gridcenter.or.kr`
  - SPF(TXT): `kisti.re.kr` SPF 레코드에 위 IP 추가 (담당 부서 협조)

## 7. 코드 개요
핵심 로직은 `cert_notifier.py`에 있으며, `cert`/`csr` 테이블을 조인해 만료일이 14·7·3·1일 남은 인증서를 조회하고 대상자에게 HTML 이메일을 발송합니다.
