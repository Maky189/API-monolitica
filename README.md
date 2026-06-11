# Microserviços com API Gateway, escala horizontal e segurança

Sistema didático que demonstra a evolução de uma arquitetura monolítica para **microserviços independentes** comunicando por HTTP real, com **escala horizontal** (load balancer round-robin + réplicas), **persistência em Postgres** e uma camada completa de **segurança** (autenticação JWT, autenticação serviço-a-serviço, rate limiting e cabeçalhos de segurança).

> O projeto foi desenvolvido em duas partes. **Parte 1** apresentou as arquiteturas monolítica e de microserviços. **Parte 2** removeu o monólito e focou em desempenho sob carga, escalabilidade horizontal e segurança — que é o que este README documenta.

## Visão geral

A aplicação modela um fluxo simples de e-commerce: um cliente autentica-se, cria um pedido e o sistema decide se o pagamento é aprovado. Cada responsabilidade vive num serviço próprio:

- **Gateway** (`:5000`) — porta de entrada pública. Autentica o pedido (JWT), aplica rate limiting, valida o body, injeta o token interno e encaminha para o Order Service.
- **Auth Service** (`:5002`) — emite tokens JWT contra credenciais (palavras-passe guardadas com hash).
- **Order Service** (`:5001`) — lógica de negócio. Cria o pedido, persiste em Postgres, trata idempotência e chama o Payment Service via load balancer round-robin com retries.
- **Payment Service** (`:5003`, **3 réplicas**) — decide aprovação do pagamento. Stateless, identifica-se pelo `INSTANCE_ID`.
- **Postgres** — estado persistente (pedidos + chaves de idempotência), partilhado por todos os workers.

## Arquitetura

```
  Cliente
    │ 1) POST /auth/token  ──────────────►  Auth Service :5002  (emite JWT)
    │
    │ 2) POST /api/orders  (Bearer JWT)
    ▼
  Gateway :5000
    │  • valida JWT          • rate limit (20/min)
    │  • valida body         • injeta X-Internal-Token
    │  POST /orders  (HTTP, token interno)
    ▼
  Order Service :5001  ──────(SQLAlchemy)──────►  Postgres
    │  _next_payment_url()  → round-robin           (orders,
    │                                                idempotency_keys)
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
 payment-1     payment-2     payment-3      :5003 (3 réplicas, stateless)
   (cada chamada vai com timeout curto + 3 retries com backoff)
```

## Componentes

### Gateway — `gateway/app.py` `:5000`
Único serviço exposto ao exterior. Responsabilidades de segurança e roteamento:
- **JWT obrigatório** em `POST /api/orders` (decorador `@require_jwt`, algoritmo HS256).
- **Rate limiting** com Flask-Limiter (`20/minuto` na rota de pedidos; limites globais por dia/hora).
- **Validação e saneamento** do body (`item`, `price`), com limite de tamanho do pedido (`MAX_CONTENT_LENGTH` = 1 MB).
- **Cabeçalhos de segurança** em todas as respostas (`X-Content-Type-Options`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Strict-Transport-Security`, `Content-Security-Policy`, `Referrer-Policy`, remove `Server`/`X-Powered-By`).
- **CORS** configurável via `ALLOWED_ORIGINS`.
- Propaga `Idempotency-Key` e injeta `X-Internal-Token` ao chamar o Order Service.

### Auth Service — `auth_service/app.py` `:5002`
- `POST /auth/token` — valida `username`/`password` e devolve um **JWT** assinado com `JWT_SECRET`, com expiração configurável (`JWT_EXPIRY_HOURS`).
- Palavras-passe guardadas com **hash** (`werkzeug.security`), nunca em texto simples.
- Regista tentativas de login inválidas.

### Order Service — `order_service/app.py` `:5001`
- `POST /orders` — protegido por **token interno** (`@require_internal_token`); só o Gateway o pode chamar.
- **Load balancer round-robin** manual (`_next_payment_url`, `itertools.cycle` + `threading.Lock`) sobre `PAYMENT_SERVICE_URLS`.
- **Retries com backoff exponencial** (`tenacity`, 3 tentativas) e **timeout curto** na chamada de pagamento — se uma réplica cai, o retry seguinte vai para outra.
- **Idempotência**: com `Idempotency-Key`, retries não criam pedidos duplicados (resposta cacheada em Postgres).
- Persistência via `repository.py` (SQLAlchemy + Postgres).

### Payment Service — `payment_service/app.py` `:5003` (×3)
- `POST /payment` — protegido por **token interno**. Aprova `price > 0`, rejeita `price == 0`.
- **Stateless** — replicado em `payment-1/2/3`; cada resposta traz o seu `instance` para tornar o balanceamento observável.

### Suporte
- `logger_config.py` — logging centralizado (`asctime [levelname] nome: mensagem`).
- `repository.py` — modelos `Order` e `IdempotencyRecord` e acesso a dados.

## Segurança (Parte 2)

| Camada | Mecanismo | Onde |
|---|---|---|
| Autenticação do cliente | JWT (HS256) com expiração | Auth Service emite, Gateway valida |
| Credenciais | Hash de password (`werkzeug`) | Auth Service |
| Autenticação serviço-a-serviço | `X-Internal-Token` partilhado | Order & Payment Services |
| Abuso / força bruta | Rate limiting (Flask-Limiter) | Gateway |
| Hardening HTTP | Cabeçalhos de segurança + CORS | Gateway |
| Entrada maliciosa | Validação, saneamento e `MAX_CONTENT_LENGTH` | Gateway |
| Duplicação sob retry | Idempotency-Key + Postgres | Order Service |

Todos os segredos (`JWT_SECRET`, `INTERNAL_SERVICE_TOKEN`, passwords) são lidos do ambiente — ver `.env.example`.

## Decisões de arquitetura — porquê

Esta secção explica **porque** cada peça central foi escolhida e **porque se sobressai** face às alternativas. A regra que guiou todas as decisões: *resolver um gargalo concreto com a solução mais simples que ainda dá o ganho pretendido.*

### Load balancer round-robin

**Porque usamos.** A carga é homogénea — cada pedido de pagamento custa aproximadamente o mesmo. Quando todas as requisições têm custo semelhante, alternar sequencialmente entre as réplicas já distribui o trabalho de forma uniforme, sem precisar de medir nada. É uma decisão O(1), sem estado partilhado sobre o tráfego.

**Porque se sobressai.**
- *vs least-connections* — least-connections só compensa quando as requisições têm durações muito diferentes; aqui não têm, e ainda exigiria manter e sincronizar a contagem de conexões abertas por réplica (estado + contention). Custo sem benefício.
- *vs weighted* — só faz sentido se as réplicas tivessem capacidades diferentes; as nossas são idênticas, logo os pesos seriam todos iguais (= round-robin).
- *vs aleatório* — distribui bem só em média e com muitas amostras; o round-robin dá distribuição exata e previsível, o que torna o efeito **observável** no load test (as 3 réplicas aparecem com contagens iguais).

### Load balancer dentro do Order Service (e não nginx/HAProxy)

**Porque usamos.** O objetivo é didático: tornar o balanceamento **visível e explícito** no código (`_next_payment_url`), sem introduzir mais uma peça de infraestrutura para configurar e operar.

**Porque se sobressai (neste contexto).** Um nginx/HAProxy/service mesh seria a escolha de produção, mas esconderia a lógica numa caixa preta e adicionaria um componente a gerir. Para demonstrar o conceito, mantê-lo no serviço é mais transparente. **Trade-off assumido:** em produção o balanceador não deve viver dentro da aplicação (é um ponto de acoplamento e um nó interno) — o passo seguinte natural é movê-lo para nginx/HAProxy à frente das réplicas.

### Réplicas nomeadas (payment1/2/3) em vez de `docker compose --scale`

**Porque usamos.** Cada réplica tem um `INSTANCE_ID` e um hostname próprios, e devolve o seu `instance` na resposta. Isso torna o round-robin **demonstrável**: vê-se exatamente qual réplica respondeu cada pedido. Com `--scale` as réplicas seriam anónimas e o efeito do balanceador ficaria invisível.

### Gunicorn em vez do servidor de desenvolvimento do Flask

**Porque usamos.** O servidor dev do Flask serve uma requisição de cada vez por thread e não é seguro para produção. O Gunicorn corre vários *workers* (processos independentes, cada um com o seu GIL), dando **paralelismo real** — é a escala vertical do processo.

**Porque se sobressai.** É o gargalo mais barato de remover: uma flag (`-w 4`) multiplica a capacidade de servir requisições em simultâneo, sem mudar uma linha de lógica.

### Serviços stateless + estado em Postgres

**Porque usamos.** Escala horizontal só funciona se as instâncias forem **stateless** — qualquer réplica tem de poder responder a qualquer requisição. Por isso o estado (pedidos, chaves de idempotência) foi externalizado para o Postgres, partilhado por todos os workers e réplicas.

**Porque se sobressai.**
- *vs estado em memória* — dois workers a gravar na mesma estrutura em memória colidem (race condition), e cada réplica teria uma visão diferente dos dados. Externalizar remove a corrida e dá uma única fonte de verdade.
- *vs ficheiro local* — não é partilhável entre containers nem entre máquinas. A base de dados é o backend partilhado que a replicação exige.

### Idempotency-Key

**Porque usamos.** Como há *retries*, o mesmo pedido pode chegar mais do que uma vez (semântica *at-least-once*). Sem proteção, isso criaria pedidos e pagamentos duplicados. Com uma `Idempotency-Key`, a primeira resposta é guardada e as repetições devolvem-na em vez de reprocessar.

**Porque se sobressai.** É o padrão da indústria para operações não-idempotentes (pagamentos) sob retry. A alternativa — não ter nada — torna os retries perigosos; a alternativa de desligar retries sacrifica a resiliência. A idempotência permite ter **as duas coisas**: retries seguros.

### Timeout curto + retries com backoff (tenacity)

**Porque usamos.** Uma chamada síncrona lenta segura um worker e propaga lentidão em cascata para montante. Um **timeout curto** corta a espera; **retries com backoff** dão uma segunda hipótese sem martelar o serviço; e como há réplicas, o retry seguinte cai noutra instância.

**Porque se sobressai.**
- *vs sem timeout* — uma dependência pendurada esgotaria os workers e derrubaria o sistema inteiro.
- *vs retry imediato sem backoff* — em sobrecarga, repetir de imediato piora o problema (efeito *thundering herd*); o backoff exponencial dá tempo ao serviço para recuperar.

### Autenticação por JWT (HS256)

**Porque usamos.** O JWT é **stateless**: leva a identidade assinada dentro do próprio token. O Gateway valida a assinatura e a expiração localmente, sem ter de consultar o Auth Service nem um armazenamento de sessões a cada pedido.

**Porque se sobressai.** *vs sessões no servidor* — sessões exigem um store partilhado (e.g. Redis) consultado em cada requisição, o que recria um ponto central de estado e contraria a escala horizontal. O JWT remove essa dependência: qualquer réplica do Gateway valida o token sozinha.

### Token interno serviço-a-serviço

**Porque usamos.** Os serviços internos (Order, Payment) nunca devem aceitar chamadas diretas do exterior — só do Gateway. Um segredo partilhado (`X-Internal-Token`) garante que um pedido que não passe pelo Gateway é rejeitado com `403`.

**Porque se sobressai.** É a defesa mínima e suficiente para fechar a rede interna neste âmbito. *vs mTLS* — TLS mútuo seria mais robusto (identidade criptográfica por serviço), mas traz gestão de certificados que excede o objetivo do trabalho. **Trade-off assumido:** mTLS ou um service mesh seriam o passo de produção.

### API Gateway como único ponto de entrada

**Porque usamos.** Centralizar autenticação, rate limiting, validação e cabeçalhos de segurança num único serviço evita duplicar essas preocupações em cada microserviço e **reduz a superfície de ataque** — só uma porta está exposta.

**Porque se sobressai.** *vs expor cada serviço diretamente* — espalharia a lógica de segurança por todos os serviços (mais código repetido, mais pontos para errar) e abriria várias portas ao exterior. O Gateway concentra a fronteira de confiança num só lugar.

## Como executar

### 1. Configurar variáveis de ambiente
```bash
cp .env.example .env
# edite .env e defina segredos fortes (openssl rand -hex 64, etc.)
```

### 2. Subir todo o ambiente
```bash
docker compose up --build
```
Sobem: `gateway`, `auth-service`, `order-service`, `payment1/2/3` e `db` (Postgres).

### 3. Obter um token
```bash
curl -X POST http://localhost:5002/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```
Resposta:
```json
{ "token": "eyJhbGciOi...", "expires_in": 86400 }
```

### 4. Criar um pedido (autenticado)
```bash
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"item": "Mouse", "price": 50}'
```
Resposta:
```json
{
  "order": { "id": 1, "item": "Mouse", "price": 50 },
  "payment_status": "APPROVED",
  "payment_instance": "payment-2"
}
```

## Cenários de teste

| Situação | Resultado |
|---|---|
| `price > 0` | `APPROVED` |
| `price = 0` | `REJECTED` |
| Sem `item`/`price` | `400 Bad Request` |
| Sem token / token inválido | `401 Unauthorized` |
| Demasiados pedidos | `429 Too Many Requests` |
| Body > 1 MB | `413 Payload Too Large` |
| Rota inexistente | `404 Not Found` |
| Método errado | `405 Method Not Allowed` |

## Testes automatizados

**Unitários** (`tests/test_order_service.py`) — isolam o Order Service com `unittest.mock` (mock de `_call_payment` e SQLite em memória). Cobrem aprovação/rejeição, falha do pagamento (`UNKNOWN`) e a proteção por token interno (403). Não precisam de servidores a correr.

**Integração** (`tests/test_integration.py`) — fazem requisições HTTP reais contra a stack a correr. Cobrem fluxo completo, autenticação (401), credenciais inválidas, cabeçalhos de segurança e idempotência. **Exigem `docker compose up` a correr.**

```bash
# Unitários (sem servidores)
python -m pytest tests/test_order_service.py -v

# Integração (requer docker compose up)
python -m pytest tests/test_integration.py -v
```

## Escala horizontal e teste de carga (Parte 2)

O relatório técnico completo (fundamentos, diagramas e análise comparativa) está em `relatorio.pdf`. Resumo da implementação:

- **Gunicorn** como servidor WSGI de produção, com vários workers por serviço (escala vertical do processo).
- **Replicação** do Payment Service em três instâncias independentes (`payment1/2/3`).
- **Load balancer round-robin** dentro do Order Service (`_next_payment_url`), configurado via `PAYMENT_SERVICE_URLS`.
- **Postgres** externaliza o estado: vários workers partilham o mesmo armazenamento sem corridas.
- **Idempotência + timeout + retries** para resiliência sob carga.

### Executar teste de carga
```bash
python loadtest.py -n 100 -c 10    # baseline
python loadtest.py -n 500 -c 100   # stress
```
O `loadtest.py` imprime throughput, latência (min/média/mediana/p95/p99/máx), códigos HTTP e a **distribuição por instância** — evidenciando o round-robin entre `payment-1/2/3`.

### Demonstrar com e sem escala
```bash
# Sem escala: uma única réplica
PAYMENT_SERVICE_URLS=http://payment1:5003/payment docker compose up --build

# Com escala: três réplicas (default do compose)
docker compose up --build
```
Compare p95/p99 e throughput entre os dois cenários — é o que evidencia o ganho da escala horizontal.

## Estrutura de ficheiros

```
.
├── gateway/                # API Gateway :5000 — JWT, rate limit, headers, CORS
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── auth_service/           # Auth :5002 — emite JWT, hash de passwords
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── order_service/          # Order :5001 — round-robin, retries, idempotência
│   ├── app.py
│   ├── repository.py       # SQLAlchemy: Order + IdempotencyRecord
│   ├── Dockerfile
│   └── requirements.txt
├── payment_service/        # Payment :5003 — stateless, replicado ×3
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── tests/
│   ├── test_order_service.py   # unitários (mock + token interno)
│   └── test_integration.py     # integração (HTTP real, auth, segurança)
├── docker-compose.yml      # gateway + auth + order + 3×payment + Postgres
├── logger_config.py        # logging centralizado
├── loadtest.py             # teste de carga (latência + distribuição)
├── .env.example            # segredos e configuração
└── relatorio.pdf           # relatório técnico da Parte 2
```

## Stack

Python · Flask · Gunicorn · PyJWT · Flask-Limiter · Flask-CORS · SQLAlchemy · Postgres · Tenacity · Docker Compose
