<div align="center">
  <img src="https://via.placeholder.com/150x150" alt="PROGEN Logo" width="150"/>
  <h1>PROGEN</h1>
  <p>AI-based Document Processing and Chat System<br>AI 기반 문서 처리 및 채팅 시스템</p>
  
  ![Version](https://img.shields.io/badge/version-1.0.0-blue)
  ![License](https://img.shields.io/badge/license-MIT-green)
  ![Python](https://img.shields.io/badge/Python-3.11.9-yellow)
  ![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Latest-336791)
</div>

## 📋 Table of Contents / 목차
- [Overview / 개요](#overview--개요)
- [Key Features / 주요 기능](#key-features--주요-기능)
- [Technology Stack / 기술 스택](#technology-stack--기술-스택)
- [Installation Guide / 설치 방법](#installation-guide--설치-방법)
- [Project Structure / 프로젝트 구조](#project-structure--프로젝트-구조)
- [Key Module Descriptions / 주요 모듈 설명](#key-module-descriptions--주요-모듈-설명)
- [API Endpoints / API 엔드포인트](#api-endpoints--api-엔드포인트)
- [Supported Document Processing Formats / 문서 처리 지원 형식](#supported-document-processing-formats--문서-처리-지원-형식)
- [Database Schema / 데이터베이스 스키마](#database-schema--데이터베이스-스키마)
- [License / 라이선스](#license--라이선스)
- [How to Contribute / 기여 방법](#how-to-contribute--기여-방법)
- [Contact / 연락처](#contact--연락처)

## 🌟 Overview / 개요

PROGEN is a web application that processes various document formats and provides a conversational interface using AI models. Users can upload documents in various formats such as PDF, HWP, DOCX, Excel, etc., extract text, and chat with AI assistants.

PROGEN은 다양한 문서 형식을 처리하고 AI 모델을 활용한 대화형 인터페이스를 제공하는 웹 애플리케이션입니다. 사용자는 PDF, HWP, DOCX, Excel 등 다양한 형식의 문서를 업로드하여 텍스트를 추출하고, AI 어시스턴트와 대화할 수 있습니다.

<div align="center">
  <img src="https://via.placeholder.com/800x400" alt="PROGEN Screenshot" width="80%"/>
  <p><i>PROGEN Application Interface / PROGEN 애플리케이션 인터페이스</i></p>
</div>

## ✨ Key Features / 주요 기능

* 📄 **Support for Various Document Formats**: Process PDF, HWP, HWPX, DOC, DOCX, Excel files
* 📄 **다양한 문서 형식 지원**: PDF, HWP, HWPX, DOC, DOCX, Excel 파일 처리

* 🤖 **AI Chat Interface**: Support for various AI models including Meta, Claude, Gemini
* 🤖 **AI 채팅 인터페이스**: Meta, Claude, Gemini 등 다양한 AI 모델 지원

* 🔐 **User Authentication System**: JWT-based login and permission management
* 🔐 **사용자 인증 시스템**: JWT 기반 로그인 및 권한 관리

* 💬 **Real-time Communication**: Real-time chat via WebSocket
* 💬 **실시간 통신**: WebSocket을 통한 실시간 채팅

* 📱 **Responsive Web Design**: Support for mobile and desktop environments
* 📱 **반응형 웹 디자인**: 모바일 및 데스크톱 환경 지원

## 🛠️ Technology Stack / 기술 스택

<table>
  <tr>
    <td><b>Backend / 백엔드</b></td>
    <td>FastAPI, Python 3.11.9</td>
  </tr>
  <tr>
    <td><b>Frontend / 프론트엔드</b></td>
    <td>HTML, CSS, JavaScript, Tailwind CSS</td>
  </tr>
  <tr>
    <td><b>Database / 데이터베이스</b></td>
    <td>PostgreSQL, SQLAlchemy</td>
  </tr>
  <tr>
    <td><b>Authentication / 인증</b></td>
    <td>JWT (JSON Web Tokens)</td>
  </tr>
  <tr>
    <td><b>Document Processing / 문서 처리</b></td>
    <td>PyPDF2, HWPLoader, pandas, python-docx</td>
  </tr>
  <tr>
    <td><b>AI Model Integration / AI 모델 통합</b></td>
    <td>Claude, Meta, Gemini</td>
  </tr>
</table>

## 📥 Installation Guide / 설치 방법

### Requirements / 요구 사항

* Python 3.11.9
* PostgreSQL
* Required external libraries (refer to requirements.txt) / 필요한 외부 라이브러리 (requirements.txt 참조)

### Installation Steps / 설치 단계

<details>
<summary>1. Clone the repository / 저장소 클론</summary>

```bash
git clone https://github.com/EnzoMH/aiapp.git
cd aiapp
```
</details>

<details>
<summary>2. Create and activate virtual environment / 가상 환경 생성 및 활성화</summary>

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```
</details>

<details>
<summary>3. Install dependencies / 의존성 설치</summary>

```bash
pip install -r requirements.txt
```
</details>

<details>
<summary>4. PostgreSQL Setup / PostgreSQL 설정</summary>

* Create PostgreSQL database / PostgreSQL 데이터베이스 생성

```sql
CREATE DATABASE progen;
CREATE USER progen_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE progen TO progen_user;
```
</details>

<details>
<summary>5. Set Environment Variables / 환경 변수 설정</summary>

Create a .env file and set the following variables:
.env 파일을 생성하고 다음 변수를 설정합니다:

```
JWT_SECRET_KEY=your_secret_key
PSQL_URL=postgresql://progen_user:your_password@localhost:5432/progen
```
</details>

<details>
<summary>6. Initialize Database / 데이터베이스 초기화</summary>

```bash
python -c "from dbcon import Base, engine; Base.metadata.create_all(bind=engine)"
```
</details>

<details>
<summary>7. Run the Application / 애플리케이션 실행</summary>

```bash
python app.py
```
</details>

## 📂 Project Structure / 프로젝트 구조

```
PROGEN/
├── static/                      # Static files directory
│   ├── css/                     # 정적 파일 디렉토리
│   │   └── style.css           # Main stylesheet
│   │                           # 메인 스타일시트
│   ├── js/
│   │   ├── home.js             # Homepage script
│   │   │                       # 홈페이지 스크립트
│   │   └── login.js            # Login page script
│   │                           # 로그인 페이지 스크립트
│   ├── image/                  # Image resources directory
│   │                           # 이미지 리소스 디렉토리
│   ├── home.html               # Homepage
│   │                           # 홈페이지
│   └── login.html              # Login page
│                               # 로그인 페이지
│
├── backend/                     # Backend core directory
│   │                           # 백엔드 코어 디렉토리
│   ├── login.py                # Login/authentication utilities
│   │                           # 로그인/인증 관련 유틸리티
│   ├── dbtest.py               # Database test
│   │                           # 데이터베이스 테스트
│   └── utils/                  # Utility functions directory
│       │                       # 유틸리티 함수 디렉토리
│       ├── agent/              # AI agent related files
│       │                       # AI 에이전트 관련 파일
│       ├── crawl/              # Crawler related files
│       │                       # 크롤러 관련 파일
│       └── prop/               # Document processing and proposal generation
│                               # 문서 처리 및 제안서 생성 관련 파일
│
├── app.py                      # FastAPI main application
│                               # FastAPI 메인 애플리케이션
├── chat.py                     # Chat feature implementation
│                               # 채팅 관련 기능 구현
├── docpro.py                   # Document processing module
│                               # 문서 처리 모듈
├── dbcon.py                    # Database connection and model definition
│                               # 데이터베이스 연결 및 모델 정의
└── requirements.txt            # Project dependency list
                                # 프로젝트 의존성 목록
```

## 📚 Key Module Descriptions / 주요 모듈 설명

<details>
<summary><b>app.py</b></summary>

FastAPI-based main application file, including route definitions, middleware settings, and WebSocket endpoints.

FastAPI 기반의 메인 애플리케이션 파일로, 라우트 정의, 미들웨어 설정, WebSocket 엔드포인트 등을 포함합니다.
</details>

<details>
<summary><b>docpro.py</b></summary>

A module that processes various document formats (PDF, HWP, DOCX, Excel, etc.) to extract text. It provides dedicated processing functions for each file format.

다양한 문서 형식(PDF, HWP, DOCX, Excel 등)을 처리하여 텍스트를 추출하는 모듈입니다. 각 파일 형식별로 전용 처리 함수를 제공합니다.
</details>

<details>
<summary><b>chat.py</b></summary>

A module that manages conversations with AI models, providing message processing, session management, and AI model integration.

AI 모델과의 대화를 관리하는 모듈로, 메시지 처리, 세션 관리, AI 모델 통합 등의 기능을 제공합니다.
</details>

<details>
<summary><b>dbcon.py</b></summary>

Defines PostgreSQL database connections and ORM models. It uses SQLAlchemy to manage tables such as User, Session, Message, Memory, etc.

PostgreSQL 데이터베이스 연결 및 ORM 모델을 정의합니다. SQLAlchemy를 사용하여 User, Session, Message, Memory 등의 테이블을 관리합니다.
</details>

<details>
<summary><b>backend/login.py</b></summary>

Implements JWT-based user authentication and permission management.

JWT 기반의 사용자 인증 및 권한 관리 기능을 구현합니다.
</details>

## 🔌 API Endpoints / API 엔드포인트

### Web Pages / 웹 페이지
* `GET /`: Login page / 로그인 페이지
* `GET /home`: Main homepage / 메인 홈페이지

### Authentication API / 인증 API
* `POST /api/login`: User login / 사용자 로그인
* `GET /api/me`: View current user info / 현재 사용자 정보 조회
* `GET /api/admin/users`: View all user list (admin only) / 모든 사용자 목록 조회 (관리자 전용)

### WebSocket
* `WebSocket /chat`: Real-time chat connection / 실시간 채팅 연결

### File Processing / 파일 처리
* `POST /mainupload`: File upload and text extraction / 파일 업로드 및 텍스트 추출

## 📑 Supported Document Processing Formats / 문서 처리 지원 형식

<table>
  <tr>
    <th>Format / 형식</th>
    <th>Processing Method / 처리 방법</th>
  </tr>
  <tr>
    <td><b>PDF</b></td>
    <td>Processed using PyMuPDF or PyPDF2 / PyMuPDF 또는 PyPDF2를 사용하여 처리</td>
  </tr>
  <tr>
    <td><b>HWP/HWPX</b></td>
    <td>Processed using HWPLoader / HWPLoader를 사용하여 처리</td>
  </tr>
  <tr>
    <td><b>DOCX</b></td>
    <td>Processed using python-docx / python-docx를 사용하여 처리</td>
  </tr>
  <tr>
    <td><b>DOC</b></td>
    <td>Processed using antiword or binary analysis / antiword 또는 바이너리 분석을 통해 처리</td>
  </tr>
  <tr>
    <td><b>Excel</b></td>
    <td>Processed using pandas / pandas를 사용하여 처리</td>
  </tr>
</table>

## 💾 Database Schema / 데이터베이스 스키마

<table>
  <tr>
    <th>Table / 테이블</th>
    <th>Description / 설명</th>
  </tr>
  <tr>
    <td><b>users</b></td>
    <td>User information (user_id, password, role, created_at, last_login) / 사용자 정보 (user_id, password, role, created_at, last_login)</td>
  </tr>
  <tr>
    <td><b>sessions</b></td>
    <td>Chat session information (session_id, user_id, model, system_prompt, created_at, last_updated, active) / 채팅 세션 정보 (session_id, user_id, model, system_prompt, created_at, last_updated, active)</td>
  </tr>
  <tr>
    <td><b>messages</b></td>
    <td>Chat messages (message_id, session_id, role, content, timestamp) / 채팅 메시지 (message_id, session_id, role, content, timestamp)</td>
  </tr>
  <tr>
    <td><b>memories</b></td>
    <td>User memory (memory_id, user_id, content, keywords, importance, status, timestamp) / 사용자 메모리 (memory_id, user_id, content, keywords, importance, status, timestamp)</td>
  </tr>
</table>

## 📜 License / 라이선스

This project is distributed under the MIT license.

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🤝 How to Contribute / 기여 방법

1. Fork this repository / 이 저장소를 포크합니다.
2. Create a new feature branch (git checkout -b feature/amazing-feature) / 새 기능 브랜치를 생성합니다 (git checkout -b feature/amazing-feature).
3. Commit your changes (git commit -m 'Add some amazing feature') / 변경 사항을 커밋합니다 (git commit -m 'Add some amazing feature').
4. Push to the branch (git push origin feature/amazing-feature) / 브랜치에 푸시합니다 (git push origin feature/amazing-feature).
5. Create a Pull Request / Pull Request를 생성합니다.

## 📞 Contact / 연락처

Project Manager: [isfs003@gmail.com] / 프로젝트 관리자: [isfs003@gmail.com]  
GitHub: [https://github.com/EnzoMH/aiapp](https://github.com/EnzoMH/aiapp)

---

<div align="center">
  <p>© 2023 PROGEN. All Rights Reserved.</p>
</div>
