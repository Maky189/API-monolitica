Sistema monolítico com microserviços

Este repositório é um exemplo que mostra, como dividir responsabilidades entre três peças principais: o Gateway, o Monólito e o PaymentService. O código é para entender os conceitos básicos sem muita complexidade.

## Visão geral

- O Gateway recebe pedidos do cliente e encaminha para a parte responsável.
- O Monólito contém a lógica de negócio (cria pedidos, aplica regras).
- O PaymentService decide se o pagamento é aprovado ou não.

Os componentes ficam em processo neste exemplo, o que facilita testes. Para um sistema real, cada peça poderia funcionar separadamente e se comunicar por rede.

## Gateway

O Gateway é a ponte de entrada do sistema. Ele recebe a requisição, faz validações básicas, registra logs e encaminha para onde for preciso. Em `gateway.py` há a classe `Gateway` com o método `handle_request(path, data)`. Por exemplo, `/api/orders` é enviado para `Monolith.create_order(data)`. No projeto o Gateway é simples mas em produção ele normalmente vira um servidor HTTP.

## Monólito

O Monólito concentra a lógica do domínio. Em `monolith.py`, o método `create_order(self, data)` monta um objeto `order` (com `id`, `item`, `price`), registra logs e chama o `payment_service` para processar o pagamento. A persistência aqui é simulada em memória.


## PaymentService

Em `payment_service.py`, o `PaymentService.process_payment(order)` aprova pagamentos com `price > 0`. Isso facilita testar fluxos aprovados e recusados.

Em um produto real, esse serviço teria integração com gateways de pagamento, tratamento e logs de transação e cuidados de segurança.

## Como executar (cliente/runner)

O `main.py` monta os componentes, configura o logging e faz uma chamada de exemplo ao `Gateway.handle_request`. É útil para fazer uma demonstração local sem precisar de servidores HTTP.

## Ideia da arquitetura

Separar o sistema em serviços ajuda a manter e escalar partes diferentes independentemente. Por outro lado, aumenta a complexidade operacional (mais coisas para monitorar e gerenciar).  A comunicação é feita por chamadas em memória (mais simples). Se passar para comunicação por rede (HTTP), aparecem questões como latência, falhas de rede e necessidade de logs/monitoramento.

Uma escolha é como lidar com o pagamento: confirmar o pedido só depois do pagamento (mais seguro) ou aceitar o pedido e reconciliar depois (mais rápido, mas mais complexo).

## Estrutura de arquivos

- `gateway.py`: classe `Gateway` e `handle_request(path, data)`
- `monolith.py`: classe `Monolith` com `create_order(self, data)` — cria pedidos e chama o payment service.
- `payment_service.py`: classe `PaymentService` com `process_payment(order)` — lógica de aprovação.
- `main.py`: script de demonstração para rodar o fluxo localmente.
- `logger_config.py`: configuração do logging usada pelo projeto.
- `tests/test_monolith.py`: testes unitários que usam um fake `PaymentService`.
- `test_integration.py`: teste de integração em processo (fim-a-fim).

## Fluxo (explicado de forma simples)

1. O cliente envia um `POST /api/orders` com `item` e `price`.
2. O Gateway valida os dados e encaminha para o Monólito.
3. O Monólito cria o pedido e chama o PaymentService.
4. O PaymentService retorna `APPROVED` ou `REJECTED`.
5. O Monólito responde ao Gateway, que devolve o resultado ao cliente.

Deve-se decidir sobre timeouts e como tratar erros (tentar de novo, rejeitar a operação, ou enfileirar para reconciliação).

## Testes

Este projeto tem dois tipos de teste:
- Unitários (`tests/test_monolith.py`): isolam o Monólito usando um fake do PaymentService.
- Integração (`test_integration.py`): roda os componentes juntos em processo para validar o fluxo completo.

Comandos de exemplo:

```bash
# Testes unitários
python -m pytest tests/test_monolith.py -v

# Teste de integração
python -m pytest test_integration.py -v

# Os 2
python -m pytest tests/test_monolith.py test_integration.py -v
```
## Dependências

```bash
pip install flask requests pytest
```