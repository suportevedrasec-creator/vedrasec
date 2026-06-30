# Sistema Vedra SEC — Guia de Instalação e Deploy

## Estrutura do Projeto

```
sistema_vedra/
├── app.py               ← Aplicação Flask (backend + rotas)
├── models.py            ← Modelos do banco de dados
├── import_planilha.py   ← Script de importação da planilha
├── requirements.txt     ← Dependências Python
├── templates/           ← Interfaces HTML
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── cadastros.html
│   ├── esteira.html
│   ├── acordos.html
│   ├── indices.html
│   └── relatorio_diario.html
└── static/
    ├── css/style.css    ← Estilo visual jurídico
    └── js/app.js        ← JavaScript frontend
```

---

## 1. Instalação Local (Windows)

### Pré-requisitos
- Python 3.10 ou superior  
- pip instalado

### Passos

```bash
# 1. Entrar na pasta do sistema
cd "SISTEMA VEDRA SEC\sistema_vedra"

# 2. Criar ambiente virtual (recomendado)
python -m venv venv
venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. (Opcional) Importar dados da planilha existente
python import_planilha.py

# 5. Iniciar o sistema
python app.py
```

Acesse: **http://localhost:5000**

**Credenciais padrão:**  
- E-mail: `admin@vedrasec.com.br`  
- Senha: `VedraSec@2024`  
**Altere a senha após o primeiro acesso!**

---

## 2. Deploy Seguro — Railway (Recomendado)

Railway é a opção mais simples para hospedagem segura com HTTPS automático.

### Passos

1. Crie uma conta em [railway.app](https://railway.app)
2. Instale o CLI: `npm install -g @railway/cli`
3. Na pasta `sistema_vedra`, crie o arquivo `Procfile`:
   ```
   web: gunicorn app:app --bind 0.0.0.0:$PORT
   ```
4. Execute:
   ```bash
   railway login
   railway init
   railway up
   ```
5. Configure as variáveis de ambiente no painel Railway:
   - `SECRET_KEY` = uma string aleatória longa (ex.: gere com `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `DATABASE_URL` = Railway PostgreSQL (adicione o plugin)

---

## 3. Deploy — Render (Alternativa gratuita)

1. Crie conta em [render.com](https://render.com)
2. Conecte seu repositório GitHub
3. Crie um **Web Service** apontando para a pasta `sistema_vedra`
4. Configurações:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Variáveis de ambiente:
   - `SECRET_KEY` = string aleatória segura
   - `PYTHON_VERSION` = 3.11

---

## 4. Deploy — VPS Próprio (Mais seguro para dados sensíveis)

Para dados financeiros/jurídicos sensíveis, um VPS dedicado é o mais indicado.

### Configuração no servidor Ubuntu

```bash
# Instalar Python e Nginx
sudo apt update
sudo apt install python3-pip python3-venv nginx certbot python3-certbot-nginx -y

# Criar diretório e copiar arquivos
sudo mkdir -p /var/www/vedrasec
sudo chown $USER:$USER /var/www/vedrasec
# Copiar os arquivos para /var/www/vedrasec/

cd /var/www/vedrasec
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Criar serviço systemd
sudo nano /etc/systemd/system/vedrasec.service
```

Conteúdo do arquivo `vedrasec.service`:
```ini
[Unit]
Description=Vedra SEC - Sistema de Cobrança
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/vedrasec
Environment="SECRET_KEY=GERE_UMA_CHAVE_AQUI"
Environment="DATABASE_URL=sqlite:////var/www/vedrasec/vedra_sec.db"
ExecStart=/var/www/vedrasec/venv/bin/gunicorn app:app --workers 2 --bind 127.0.0.1:5000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Ativar serviço
sudo systemctl daemon-reload
sudo systemctl enable vedrasec
sudo systemctl start vedrasec

# Configurar Nginx
sudo nano /etc/nginx/sites-available/vedrasec
```

Conteúdo do arquivo Nginx:
```nginx
server {
    server_name seu-dominio.com.br;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/vedrasec /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Ativar HTTPS com Let's Encrypt (gratuito)
sudo certbot --nginx -d seu-dominio.com.br
```

---

## 5. Segurança

### Variáveis de ambiente obrigatórias em produção

| Variável | Descrição |
|----------|-----------|
| `SECRET_KEY` | Chave secreta Flask (mínimo 32 caracteres aleatórios) |
| `DATABASE_URL` | URL do banco (SQLite ou PostgreSQL) |

### Gerar SECRET_KEY segura

```python
python -c "import secrets; print(secrets.token_hex(32))"
```

### Backup do banco de dados

Para SQLite, faça backup periódico do arquivo `vedra_sec.db`:

```bash
# Exemplo de backup diário com cron
0 2 * * * cp /var/www/vedrasec/vedra_sec.db /backups/vedra_sec_$(date +%Y%m%d).db
```

Para produção com volume alto, migre para **PostgreSQL**.

---

## 6. Migrar para PostgreSQL (Produção)

Instale o driver:
```bash
pip install psycopg2-binary
```

Configure a variável:
```
DATABASE_URL=postgresql://usuario:senha@host:5432/vedrasec
```

O SQLAlchemy cria as tabelas automaticamente na primeira execução.

---

## 7. Primeiro Acesso

1. Acesse o sistema pelo navegador
2. Faça login com as credenciais padrão
3. Importe os dados da planilha: `python import_planilha.py`
4. Cadastre novos usuários no banco diretamente:

```python
# No shell Python com o app context ativo
from app import app, db
from models import Usuario
with app.app_context():
    u = Usuario(nome='João Silva', email='joao@empresa.com.br')
    u.set_senha('SenhaSegura123!')
    db.session.add(u)
    db.session.commit()
```

---

## 8. Módulos do Sistema

| Módulo | URL | Descrição |
|--------|-----|-----------|
| Dashboard | `/` | KPIs, gráficos e últimas movimentações |
| Cadastros | `/cadastros` | Base geral de devedores e contratos |
| Esteira | `/esteira` | Casos em andamento judicial |
| Acordos | `/acordos` | Propostas, negociações e pagamentos |
| Índices | `/indices` | IPCA, SELIC, INPC, BACEN Série 29541 |
| Relatório Diário | `/relatorio-diario` | Exportação CSV por período |
