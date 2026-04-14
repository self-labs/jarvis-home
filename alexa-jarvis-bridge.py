import json
import time
import boto3
import requests
import urllib3

# Desabilitar avisos de SSL (Útil se o DuckDNS/Cloudflare estiver estrito)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

dynamodb = boto3.resource('dynamodb')
tokens_table = dynamodb.Table('jarvis_oauth_tokens') 

def get_user_config_from_token(access_token):
    """Busca as credenciais do usuário no DynamoDB usando o accessToken."""
    if not access_token:
        return None
    try:
        response = tokens_table.get_item(Key={'access_token': access_token})
        item = response.get('Item')
        if item and item.get('type') == 'access_token':
            return item
        else:
            print(f"Token inválido ou não encontrado: {access_token}")
            return None
    except Exception as e:
        print(f"Erro ao buscar configuração do token no DynamoDB: {e}")
        return None

def call_home_assistant_async(ha_url, ha_token, event):
    """Envia o evento via Webhook, aguarda o LM Studio, e busca a resposta (Bypass Cloudflare)."""
    try:
        if not ha_url.startswith('http'):
            ha_url = f"https://{ha_url}"

        headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
            "User-Agent": "JarvisAlexaSkill/1.0" # Bypass do Bot Fight Mode do Cloudflare
        }

        # 1. Envia tudo para o Webhook (Aciona a automação no HA)
        webhook_url = f"{ha_url}/api/webhook/jarvis_skill"
        post_response = requests.post(webhook_url, json=event, headers=headers, timeout=5, verify=False)
        post_response.raise_for_status()

        # 2. Aguarda LLM processar no seu Servidor
        time.sleep(7) 

        # 3. Pesca a resposta no buffer do HA
        state_url = f"{ha_url}/api/states/input_text.jarvis_response"
        get_response = requests.get(state_url, headers=headers, timeout=5, verify=False)
        get_response.raise_for_status()

        state_data = get_response.json()
        return state_data.get('state', "O assistente processou o comando, mas não enviou texto de retorno.")

    except requests.exceptions.RequestException as e:
        print("!!!!!!!!!! ERRO DE COMUNICAÇÃO !!!!!!!!!!")
        print(f"Exceção: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status: {e.response.status_code} | Resposta: {e.response.text}")
        return "Erro de rede. Verifique se o Cloudflare está bloqueando a requisição."
    except Exception as e:
        print(f"Erro interno: {e}")
        return "Ocorreu um erro interno na comunicação com a casa."

def build_response(speech_text, should_end_session, reprompt_text=None):
    """Constrói a resposta formatada para a Alexa."""
    response = {
        'outputSpeech': {
            'type': 'PlainText',
            'text': speech_text
        },
        'shouldEndSession': should_end_session
    }
    if reprompt_text:
        response['reprompt'] = {
            'outputSpeech': {
                'type': 'PlainText',
                'text': reprompt_text
            }
        }
    return {
        'version': '1.0',
        'response': response
    }

def lambda_handler(event, context):
    """Handler principal inteligente (Delega as decisões pro Home Assistant)"""
    print(f"Event Recebido: {json.dumps(event)}")

    request_type = event['request']['type']
    access_token = event['context']['System']['user'].get('accessToken')

    # Validação de Token OAuth
    if not access_token:
        return {
            'version': '1.0',
            'response': {
                'outputSpeech': { 'type': 'PlainText', 'text': 'Vincule sua conta pelo aplicativo Alexa.' },
                'card': { 'type': 'LinkAccount' },
                'shouldEndSession': True
            }
        }

    user_config = get_user_config_from_token(access_token)
    if not user_config:
        return build_response("Sessão expirada. Por favor, revincule sua conta no aplicativo Alexa.", True)

    # Passo 1: Resposta Instantânea para Abertura
    if request_type == 'LaunchRequest':
        return build_response("Jarvis ativado. O que deseja?", False, "Estou ouvindo.")

    intent_name = event['request']['intent']['name'] if request_type == 'IntentRequest' else ''

    # Passo 2: Tratamento de Encerramento (Adicionado NoIntent)
    if intent_name in ['AMAZON.StopIntent', 'AMAZON.CancelIntent', 'AMAZON.NoIntent']:
        return build_response("Até logo.", True)

    # Interceptação de segurança nativa da Amazon
    if intent_name == 'AMAZON.FallbackIntent':
        return build_response("Comando não reconhecido pela skill. Tente dizer de outra forma.", False, "Diga um comando válido.")
    elif intent_name == 'AMAZON.HelpIntent':
        return build_response("Diga o que deseja fazer.", False, "Estou ouvindo.")

    # Processamento de Comandos (Apenas ConversationIntent chama o HA com delay)
    if intent_name == 'ConversationIntent':
        # Captura exatamente a palavra que você falou
        slots = event['request']['intent'].get('slots', {})
        spoken_text = slots.get('text', {}).get('value', '').lower().strip()
        
        # Intercepta as palavras de saída para não enviar "Nada" para a IA
        if spoken_text in ['não', 'nao', 'nada', 'encerrar', 'nenhum', 'sair']:
            return build_response("Até logo.", True)

        # Se não for palavra de saída, envia para a IA
        ha_response_text = call_home_assistant_async(
            user_config['ha_url'],
            user_config['ha_token'],
            event
        )
        return build_response(ha_response_text, False, "Mais alguma coisa?")

    return build_response("Comando não reconhecido.", False)
