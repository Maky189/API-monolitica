# Sistema monolítico com microserviços via HTTP real

Exemplo didático que demonstra como dividir responsabilidades entre três peças principais — Gateway, Monólito e PaymentService — com comunicação HTTP real usando Flask e Requests.

## Visão geral

- O **Gateway** recebe pedidos do cliente e encaminha para o Monólito.
- O **Monólito** contém a lógica de negócio (cria pedidos, aplica regras).
- O **PaymentService** decide se o pagamento é aprovado ou não.

A comunicação entre o Monólito e o PaymentService é feita por **HTTP real**: cada componente roda como um servidor Flask independente, em sua própria porta. Isso permite que, em produção, cada peça funcione em processos ou máquinas separadas sem mudança de código.

## Arquitetura

```
  Cliente
    │
    │ POST /api/orders  (HTTP :5000)
    ▼
  Gateway  :5000
    │
    │ chamada Python direta
    ▼
  Monólito
    │
    │ POST /payment  (HTTP :5001)
    ▼
  PaymentService  :5001
```

## Componentes

### Gateway — `gateway.py` `:5000`

Servidor Flask que expõe a rota `POST /api/orders`. Valida o body recebido (campos `item` e `price` são obrigatórios), registra logs e encaminha para o Monólito. Retorna erros em JSON para qualquer situação inválida (400, 404, 405).

### Monólito — `monolith.py`

Contém a lógica de domínio. O método `create_order(data)` monta o objeto do pedido e chama o PaymentService via `requests.post()` para processar o pagamento. Não conhece a implementação do PaymentService — apenas o contrato HTTP.

### PaymentService — `payment_service.py` `:5001`

Servidor Flask que expõe a rota `POST /payment`. Aprova pagamentos com `price > 0` e rejeita com `price == 0`. Em um produto real, teria integração com gateways de pagamento, tratamento de transações e controles de segurança.

### Outros arquivos

- `logger_config.py` — configura o logging centralizado com formato `asctime [levelname] nome: mensagem`.

## Como executar

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Subir o ambiente

```bash
docker compose up --build
```

### Fazer uma requisição de teste

```bash
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"item": "Mouse", "price": 50}'
```

Resposta esperada:
```json
{
  "order": { "id": 1, "item": "Mouse", "price": 50 },
  "payment_status": "APPROVED"
}
```

## Usando o Postman

Com o servidor rodando, configure uma requisição no Postman:

| Campo | Valor |
|---|---|
| Method | `POST` |
| URL | `http://localhost:5000/api/orders` |
| Header | `Content-Type: application/json` |
| Body (raw JSON) | `{"item": "Mouse", "price": 50}` |

Cenários para testar:
- `price > 0` → `APPROVED`
- `price = 0` → `REJECTED`
- Body sem `item` ou `price` → `400 Bad Request`
- Rota inexistente → `404 Not Found`
- Método errado (ex: GET em `/api/orders`) → `405 Method Not Allowed`

## Testes

O projeto tem dois tipos de teste:

**Unitários** (`tests/test_monolith.py`) — isolam o Monólito usando `unittest.mock.patch` para simular o `requests.post`. Não precisam de servidores rodando, são rápidos e determinísticos.

**Integração** (`tests/test_integration.py`) — fazem requisições HTTP reais contra os servidores. **Exigem que o `main.py` esteja rodando** em outro terminal antes de executar.

### Comandos

```bash
# Testes unitários (sem servidor)
python -m pytest tests/test_monolith.py -v

# Testes de integração (requer docker compose up rodando)
python -m pytest tests/test_integration.py -v

# Todos juntos
python -m pytest tests/test_monolith.py tests/test_integration.py -v
```

## Estrutura de arquivos

```
.
├── gateway.py                  # Servidor Flask :5000
├── monolith.py                 # Lógica de pedidos, chama PaymentService via HTTP
├── payment_service.py          # Servidor Flask :5001
├── logger_config.py            # Configuração centralizada de logging
└── tests/
    ├── test_monolith.py        # Testes unitários com mock HTTP
    └── test_integration.py     # Testes de integração com servidores reais
```

## Escalabilidade (Trabalho 02)

O detalhamento completo (fundamentos, diagramas e análise comparativa) está em `relatorio.pdf`. Resumo da implementação:

- **Gunicorn** com vários workers em cada serviço (escala vertical do processo).
- **Replicação** do `payment_service` em três instâncias independentes (`payment1`, `payment2`, `payment3`).
- **Load balancer round-robin manual** dentro do monólito (`monolith._next_payment_url`), configurado via `PAYMENT_SERVICE_URLS` (lista CSV).
- Cada instância de pagamento expõe o seu `INSTANCE_ID` nos logs e na resposta JSON, para evidenciar qual réplica respondeu cada requisição.
- **Idempotency-Key** + persistência em Postgres para evitar pedidos/pagamentos duplicados sob retries.
- **Timeout + retries com backoff** (`tenacity`) na chamada do monólito para o pagamento.

### Subir o ambiente escalado

```bash
docker compose up --build
```

### Executar teste de carga

```bash
# Baseline
python loadtest.py -n 100 -c 10

# Stress
python loadtest.py -n 500 -c 100
```

O relatório do `loadtest.py` imprime tempo de resposta (min/mean/p95/p99), erros e a **distribuição por instância** — confirmando o efeito do round-robin entre `payment-1`, `payment-2` e `payment-3`.

### Demonstrar com e sem escala

```bash
# Sem escala: usar apenas uma réplica
PAYMENT_SERVICE_URLS=http://payment1:5001/payment docker compose up --build

# Com escala: três réplicas (default do compose)
docker compose up --build
```

Compare p95/p99 e throughput entre os dois cenários — é o que evidencia o ganho da escala horizontal.
