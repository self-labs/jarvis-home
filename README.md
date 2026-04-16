# Jarvis Home: Alexa + Home Assistant + LLM Local 🤖⚡

Ponte inteligente e assíncrona entre a Amazon Alexa, o Home Assistant (HA) e um LLM local (LM Studio). Resolve o problema de timeout da Alexa ao delegar o processamento ao HA, que retorna a resposta via Text-to-Speech (TTS) pelo próprio Echo.

---

## 🏗️ Arquitetura do Fluxo Assíncrono

```
Voz → Alexa → AWS API Gateway → AWS Lambda → Home Assistant → LM Studio → TTS (Alexa Media Player)
```

| #   | Etapa              | Detalhe                                                                   |
| --- | ------------------ | ------------------------------------------------------------------------- |
| 1   | **Gatilho (Voz)**  | Usuário fala o comando para a Alexa.                                      |
| 2   | **API Gateway**    | Recebe a requisição da Skill e roteia para a Lambda correta.              |
| 3   | **Lambda Bridge**  | Envia o payload ao HA via Webhook e aguarda até 15s pela resposta.        |
| 4   | **Home Assistant** | Recebe o webhook e aciona o LLM local via `Extended OpenAI Conversation`. |
| 5   | **LM Studio**      | Interpreta a intenção, monta a Tool Call e executa o serviço no HA.       |
| 6   | **TTS Assíncrono** | O HA usa o `Alexa Media Player` para fazer o Echo falar a resposta.       |

---

## 🛠️ Pré-requisitos

- **Home Assistant** exposto para a internet (Cloudflare Tunnel ou DuckDNS).
- **LM Studio** rodando localmente na mesma rede do HA.
- Conta **AWS** ativa (IAM, Lambda, DynamoDB, API Gateway).
- Conta **Alexa Developer Console** com uma Custom Skill criada.
- Integrações instaladas no HA via HACS:
  - `Extended OpenAI Conversation` — conecta ao LM Studio.
  - `Alexa Media Player` — retorno assíncrono de voz.
- **Helper:** `input_text` criado no HA com o nome exato `jarvis_response`.

---

## 🚀 Passo a Passo de Implementação

---

### Passo 1: Infraestrutura AWS

Esta é a espinha dorsal do projeto. Configure os serviços na ordem abaixo.

#### 1.1 — IAM (Identity and Access Management)

1. Acesse o console AWS → **IAM** → **Usuários** → **Criar usuário** (ex: `cateim`).
2. Selecione **Acesso programático** para gerar as chaves.
3. Anexe diretamente as 5 políticas abaixo ao usuário:

| Política                      | Finalidade                                        |
| ----------------------------- | ------------------------------------------------- |
| `AmazonDynamoDBFullAccess`    | Leitura/escrita das tabelas de tokens.            |
| `AmazonS3FullAccess`          | Dependência interna do framework.                 |
| `AWSCloudFormationFullAccess` | Deploy via SAM/CloudFormation (opcional).         |
| `AWSLambda_FullAccess`        | Deploy e gerenciamento das funções Lambda.        |
| `IAMFullAccess`               | Criação de roles para as próprias funções Lambda. |

4. Ao finalizar, **salve as chaves de acesso (Access Key ID e Secret Access Key)** — elas só aparecem uma vez.

#### 1.2 — DynamoDB (Banco de Dados)

Crie duas tabelas no console **DynamoDB → Tabelas → Criar tabela**:

| Tabela                  | Chave Primária | Tipo   | Função                                                 |
| ----------------------- | -------------- | ------ | ------------------------------------------------------ |
| `jarvis_oauth_tokens`   | `access_token` | String | **Principal** — armazena os tokens de Account Linking. |
| `alexa_jarvis_sessions` | `session_id`   | String | Auxiliar — controle de sessão (opcional).              |

> ⚠️ **Crítico:** O nome `jarvis_oauth_tokens` e o campo `access_token` são hardcoded no script `alexa-jarvis-bridge`. Não altere.

#### 1.3 — AWS Lambda

Use o runtime **Python 3.11** para ambas as funções.

##### Lambda 1: `jarvis-oauth-handler`

Responsável pelo fluxo de **Account Linking** (OAuth 2.0 entre a Skill e o HA).

1. Crie a função com o nome `jarvis-oauth-handler`.
2. Cole o código do arquivo `jarvis-oauth-handler.py` do repositório.
3. Em **Configuration → Environment variables**, adicione:

| Variável        | Valor                                                      |
| --------------- | ---------------------------------------------------------- |
| `CLIENT_ID`     | ID de cliente definido por você (ex: `jarvis-client-123`). |
| `CLIENT_SECRET` | Secret definido por você (string aleatória e segura).      |

##### Lambda 2: `alexa-jarvis-bridge`

Responsável pela **ponte de comandos** entre a Alexa e o Home Assistant.

1. Crie a função com o nome `alexa-jarvis-bridge`.
2. Cole o código do arquivo `alexa-jarvis-bridge.py` do repositório.
3. **⚠️ CRÍTICO — Timeout:** Vá em **Configuration → General configuration → Edit** e altere o Timeout de **3s para 15 segundos**. Sem isso, a Lambda encerrará antes do LLM responder.
4. **Layer `requests`:** Vá em **Layers → Add a layer** e adicione a layer da biblioteca `requests` (disponível via ARN público ou empacotando um `.zip`). A biblioteca não está disponível nativamente no runtime Python da AWS.

#### 1.4 — API Gateway

1. Acesse **API Gateway → Create API → REST API** (ex: `jarvis-registration-api`).
2. Crie os seguintes Resources e Methods:

| Resource           | Methods           | Observação                                          |
| ------------------ | ----------------- | --------------------------------------------------- |
| `/oauth/authorize` | `POST`, `OPTIONS` | Inicia o fluxo de autorização OAuth.                |
| `/oauth/exchange`  | `POST`, `OPTIONS` | Troca o authorization code pelo access token.       |
| `/register`        | `POST`, `OPTIONS` | Registra o usuário e salva credenciais no DynamoDB. |

3. Para cada rota, integre o Method `POST` à Lambda `jarvis-oauth-handler`.
4. **Habilite o CORS** em cada Resource (o método `OPTIONS` é obrigatório para o navegador do Account Linking não bloquear a chamada).
5. Clique em **Deploy API**, escolha ou crie um Stage (ex: `prod`) e anote a **Invoke URL** gerada — ela será usada na configuração da Skill.

---

### Passo 2: Alexa Developer Console

#### 2.1 — Account Linking

No console da Skill, vá em **Account Linking** e preencha usando as URLs da API Gateway criada no Passo 1.4: use os endpoints `/oauth/authorize` e `/oauth/exchange`.

Para conectar a conta do usuário ao Home Assistant, abra o arquivo `oauth.html` (hospedado na web ou localmente via `index.html`) no navegador e preencha com o `CLIENT_ID`, `CLIENT_SECRET` e a URL do seu Home Assistant. Esse fluxo registra as credenciais do HA no DynamoDB.

#### 2.2 — Interaction Model (Intents)

1. No editor de JSON da Skill, importe o arquivo `intents` do repositório — ele contém todas as intents já configuradas.
2. Certifique-se de que os dois itens abaixo estão presentes:

| Intent               | Descrição                                                                                                 |
| -------------------- | --------------------------------------------------------------------------------------------------------- |
| `AMAZON.NoIntent`    | **Crucial** para capturar a saída limpa da sessão sem gerar erro de intent não tratado.                   |
| `ConversationIntent` | Intent principal com o slot `{text}` do tipo customizado `TextoLivre` — captura qualquer fala do usuário. |

3. Salve e **Build** o modelo.

---

### Passo 3: Home Assistant

#### 3.1 — Helper

Crie o helper de estado que serve de "caixa postal" entre o LLM e a Lambda:

- **Configurações → Dispositivos e Serviços → Helpers → Criar → Texto**
- Nome: `jarvis_response`
- O `entity_id` resultante deve ser exatamente `input_text.jarvis_response`.

#### 3.2 — Integração Extended OpenAI Conversation

1. Vá em **Configurações → Dispositivos e Serviços → Extended OpenAI Conversation**.
2. Configure o endereço IP e porta do LM Studio (ex: `http://192.168.1.x:1234`).
3. No campo de **System Prompt**, cole o conteúdo do arquivo `prompt.tx` do repositório. Ele contém as **Immutable Laws** do agente, incluindo a regra `ENTITY AND DOMAIN LOGIC` — não modifique a estrutura dessas leis.
4. Exponha as entidades que a IA deve controlar em **Configurações → Assistentes de Voz → Expor Entidades** (inclua botões, scripts e cenas como `button.anime`, `scene.assistir_tv`).

#### 3.3 — Hack crítico: `tool_choice: auto`

Forçar `tool_choice: required` faz a IA alucinar comandos (ex: `get_state`) quando o usuário apenas pergunta o status de algo. A configuração `auto` devolve a liberdade para a IA decidir quando usar a Tool Call.

Edite `/config/custom_components/extended_openai_conversation/conversation.py` e garanta:

```python
        "temperature": 0.1,
        "tool_choice": "auto",
        "tools": [
```

> ⚠️ Reinicie o Home Assistant após salvar o arquivo.

#### 3.4 — Automação: Webhook + TTS

Crie uma automação no HA (**Configurações → Automações → Criar → Editar em YAML**) e cole o conteúdo do arquivo `automation.yaml` do repositório.

> 📝 Antes de salvar, substitua o `agent_id` e o nome do `media_player` da Alexa nos comentários indicados dentro do arquivo.

---

### Passo 4: LLM Local (LM Studio)

Para automação residencial confiável (Tool Calling consistente), o modelo precisa de no mínimo **3B parâmetros em quantização Q4**.

1. Baixe o modelo `google/gemma-4-e4b` (ou equivalente como Qwen 2.5 3B / Ministral 3B em Q4).
2. Carregue o modelo no LM Studio.
3. Maximize o **GPU Offload** para as camadas suportadas pela sua placa.
4. Inicie o servidor local.

**⚙️ Ajuste de hardware (GTX 970M / hardware antigo):**

A arquitetura antiga e a pouca VRAM exigem ajuste no motor (`llama.cpp`) para evitar o erro `GGML_ASSERT`. No painel de **Inference** do LM Studio, configure:

| Parâmetro      | Valor     | Motivo                                      |
| -------------- | --------- | ------------------------------------------- |
| Context Length | `2048`    | Evita sobrecarga na memória                 |
| CPU Threads    | `4`       | Máximo de núcleos físicos reais (i7-6700HQ) |
| GPU Offload    | `13`      | Limite seguro para 3GB de VRAM neste modelo |
| KV Cache       | `Unified` | Padrão                                      |

---

### Passo 5: Hacks de Usabilidade

#### Rotina na Alexa — Evitando o "Ligar Minha Casa"

O comando de voz "Ligar minha casa" é interpretado nativamente pela Amazon como uma tentativa de acionar **todos os dispositivos inteligentes** cadastrados — incluindo o portão de garagem — sem passar pelo Jarvis.

**Solução:** Crie uma Rotina no **aplicativo Alexa no celular**:

1. Abra o app Alexa → **Mais → Rotinas → Criar Rotina (+)**.
2. **Quando:** Voz → digite a frase de ativação (ex: `"Ligar minha casa"`).
3. **Ação:** Adicionar ação → **Skills** → Selecione **Jarvis** → "Abrir a skill Jarvis".
4. Salve a rotina.

A partir daí, falar "Ligar minha casa" interceptará o comando nativo da Amazon e abrirá a Skill do Jarvis, passando o controle para a IA.

---

## 📁 Arquivos do Repositório

| Arquivo                   | Descrição                                                                            |
| ------------------------- | ------------------------------------------------------------------------------------ |
| `alexa-jarvis-bridg.py`   | Código Python da Lambda principal (ponte Alexa → HA).                                |
| `jarvis-oauth-handler.py` | Código Python da Lambda de Account Linking (OAuth).                                  |
| `automation.yaml`         | YAML da automação do Home Assistant (Webhook + TTS).                                 |
| `intents`                 | JSON do Interaction Model da Alexa Skill (importe no console).                       |
| `prompt.txt`              | System Prompt completo com as Immutable Laws (cole no Extended OpenAI Conversation). |
| `oauth.html`              | Interface web para registrar as credenciais do HA na API Gateway.                    |
| `privacy.html`            | Política de Privacidade da Skill.                                                    |
| `terms.html`              | Termos de Uso da Skill.                                                              |

---

## 🐛 Troubleshooting

| Sintoma                                       | Causa Provável                                     | Solução                                                                                                |
| --------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| "Um problema ocorreu com a resposta da Skill" | Lambda estourou o timeout                          | Aumente o timeout da Lambda para 15s. Verifique se `input_text.jarvis_response` existe no HA.          |
| IA diz que executou, mas nada acontece        | IA respondeu com texto ao invés de Tool Call       | Use a `IMMUTABLE LAW 0` no System Prompt. Modelos Q3 ou <3B perdem capacidade de gerar JSONs corretos. |
| IA demora mais de 1 minuto                    | Hardware atingiu o limite (~3 t/s)                 | Reduza a complexidade dos comandos ("Ligar luz TV" ao invés de "Ligar tudo").                          |
| Erro `GGML_ASSERT` no log                     | GPU Offload além do limite da placa                | Reduza o valor gradativamente (ex: 15 → 13).                                                           |
| Vinculação de conta falha                     | CORS bloqueando a chamada do navegador             | Certifique-se de que o método `OPTIONS` está habilitado em todas as rotas do API Gateway.              |
| Token "not found" no DynamoDB                 | Tabela com nome errado ou chave primária diferente | Confirme que a tabela é `jarvis_oauth_tokens` com chave `access_token` (String).                       |
