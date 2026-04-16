# 📋 Guia de Implementação: Jarvis Home para Clientes 🤖⚡

Este documento descreve todos os passos necessários para configurar o sistema Jarvis Home (Alexa + Home Assistant + Google Gemini) do zero no ambiente de um novo cliente.

---

## 🔐 FASE 1: Credenciais e Acessos

Antes de tudo, precisamos das chaves que farão a comunicação entre os sistemas.

1. **Token do Home Assistant (HA):**
   - No HA do cliente, clique no **Perfil do Usuário** (canto inferior esquerdo).
   - Vá na aba **Segurança**.
   - Role até o final e clique em **CRIAR TOKEN** na seção "Tokens de acesso de longa duração".
   - Nomeie como `Jarvis Alexa` e **SALVE O TOKEN** (ele só aparece uma vez).

2. **API Key do Google Gemini:**
   - Acesse o [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Clique em **Create API Key**.
   - **SALVE A CHAVE** gerada.

---

## 🏠 FASE 2: Infraestrutura no Home Assistant

Agora vamos preparar a "caixa postal" e o cérebro dentro do HA.

3. **Criar o Helper (Ajudante):**
   - Vá em **Configurações > Dispositivos e Serviços > Helpers > Criar Helper > Texto**.
   - Nome: `Jarvis Response`.
   - **IMPORTANTE:** O ID da entidade deve ser exatamente `input_text.jarvis_response`.

4. **Instalar o Google Gemini:**
   - Adicione a integração oficial **Google Generative AI** no HA.
   - Insira a **API Key** gerada no passo 2.
   - Nas configurações da integração:
     - **Modelo:** Selecione `gemma-4-26b-a4b-it` (ou o modelo acordado).
     - **Nome da Entidade:** Mude para `conversation.jarvis`.
     - **Maximum tokens to return:** Altere para `10000`.
     - **Prompt:** Cole o conteúdo do arquivo `prompt.txt` do repositório.

5. **Configurar a Automação do Webhook:**
   - Crie uma nova automação e cole o YAML do arquivo `automation.yaml`.
   - **Ajustes Críticos:**
     - Certifique-se de que o `agent_id` está apontando para `conversation.jarvis`.
     - **Não** inclua a ação de TTS (Alexa Media Player), pois a resposta agora é nativa pela Skill.

6. **Expor Entidades:**
   - Vá em **Configurações > Assistentes de Voz > Google Gemini (Jarvis) > Expor Entidades**.
   - Exponha apenas o que o cliente realmente vai usar (Luzes, Ar, TV). _Evite sensores inúteis para não confundir a IA._

---

## 🗣️ FASE 3: Integração com Alexa

O passo final para dar voz ao Jarvis.

7. **Ativar a Skill:**
   - No app Alexa do cliente, procure pela Skill **Jarvis Home** e clique em **Ativar**.

8. **Account Linking (Vinculação de Conta):**
   - Na tela de login que abrir, insira:
     - **E-mail** do cliente.
     - **URL do HA** (ex: `https://casa.exemplo.com`).
     - **Token de Longa Duração** (gerado no passo 1).

9. **Configurar as Rotinas:**
   - Crie uma rotina no app Alexa para cada frase abaixo para interceptar o comando nativo:
   - **GATILHOS (Voz):**
     - "Alexa, ligar minha casa"
     - "Alexa, iniciar minha casa"
     - "Alexa, ativar minha casa"
     - "Alexa, abrir Jarvis"
     - "Alexa, ligar Jarvis"
     - "Alexa, iniciar Jarvis"
     - "Alexa, ativar Jarvis"
   - **AÇÃO (Alexa vai):** Escolha "Personalizado" e digite: `abrir minha casa`.

---

## ✅ VALIDAÇÃO FINAL

1. Diga: _"Alexa, abrir minha casa"_. Ela deve responder: _"Jarvis ativado. O que deseja?"_.
2. Peça: _"O que tem ligado?"_. Ela deve listar os aparelhos e emendar: _"Mais alguma coisa?"_.
3. Diga: _"Ligar [nome de uma luz]"_. Ela deve confirmar com apenas uma palavra (ex: "Pronto.") e perguntar novamente se deseja mais algo.
4. Diga: _"Não"_ ou _"Nada"_. Ela deve responder _"Até logo"_ e encerrar a sessão.

---

**Documentação gerada para manutenção futura.** 🛠️
