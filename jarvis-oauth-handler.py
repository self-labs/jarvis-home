import json
import boto3
import os
import time
import base64
import secrets

dynamodb = boto3.resource('dynamodb')
tokens_table = dynamodb.Table('jarvis_oauth_tokens')

# Carrega as credenciais das variáveis de ambiente
try:
    CLIENT_ID = os.environ['CLIENT_ID']
    CLIENT_SECRET = os.environ['CLIENT_SECRET']
except KeyError as e:
    print(f"Variável de ambiente essencial não configurada: {e}")
    # Em um ambiente real, isso deve impedir a execução da função
    raise Exception("CLIENT_ID e CLIENT_SECRET devem ser configurados nas variáveis de ambiente da Lambda.")

def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")
    
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
    
    if event['httpMethod'] == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}
    
    path = event['path']
    method = event['httpMethod']
    
    # Rota para criar o código de autorização temporário
    if method == 'POST' and path == '/oauth/authorize':
        try:
            body = json.loads(event['body'])
            
            # Validação dos campos obrigatórios
            if not all(k in body for k in ['email', 'ha_url', 'ha_token']):
                return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'Campos e-mail, ha_url e ha_token são obrigatórios.'})}

            auth_code = 'authcode_' + secrets.token_urlsafe(32)
            
            tokens_table.put_item(
                Item={
                    'access_token': auth_code,
                    'type': 'auth_code',
                    'email': body['email'],
                    'ha_url': body['ha_url'],
                    'ha_token': body['ha_token'],
                    'expires_at': int(time.time()) + 600,  # Expira em 10 minutos
                    'created_at': int(time.time())
                }
            )
            
            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'auth_code': auth_code})}
            
        except Exception as e:
            print(f"Erro em /oauth/authorize: {str(e)}")
            return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': 'Erro interno do servidor.'})}
    
    # Rota para trocar o código de autorização por um token de acesso permanente
    elif method == 'POST' and path == '/oauth/exchange':
        try:
            # Autenticação do cliente (Alexa)
            auth_header = event['headers'].get('Authorization', '')
            if not auth_header.startswith('Basic '):
                return {'statusCode': 401, 'headers': headers, 'body': json.dumps({'error': 'invalid_client'})}
            
            credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
            client_id, client_secret = credentials.split(':', 1)
            
            if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
                return {'statusCode': 401, 'headers': headers, 'body': json.dumps({'error': 'invalid_client'})}
            
            # Parse do corpo da requisição (form-urlencoded)
            params = {p.split('=')[0]: p.split('=')[1] for p in event['body'].split('&')}
            grant_type = params.get('grant_type')
            code = params.get('code')
            
            if grant_type != 'authorization_code' or not code:
                return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'invalid_request'})}
            
            # Busca e valida o código de autorização
            response = tokens_table.get_item(Key={'access_token': code})
            auth_code_item = response.get('Item')
            
            if not auth_code_item or auth_code_item.get('type') != 'auth_code' or auth_code_item.get('expires_at', 0) < int(time.time()):
                if auth_code_item: # Deleta se expirou ou é inválido
                    tokens_table.delete_item(Key={'access_token': code})
                return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'invalid_grant'})}
            
            # Gera e salva o token de acesso permanente
            access_token = 'token_' + secrets.token_urlsafe(32)
            
            tokens_table.put_item(
                Item={
                    'access_token': access_token,
                    'type': 'access_token',
                    'email': auth_code_item['email'],
                    'ha_url': auth_code_item['ha_url'],
                    'ha_token': auth_code_item['ha_token'],
                    'created_at': int(time.time())
                }
            )
            
            # Deleta o código de autorização usado
            tokens_table.delete_item(Key={'access_token': code})
            
            return {
                'statusCode': 200,
                'headers': {**headers, 'Content-Type': 'application/json'},
                'body': json.dumps({
                    'access_token': access_token,
                    'token_type': 'Bearer',
                    'expires_in': 31536000, # 1 ano
                    'refresh_token': 'dummy_refresh_token' # Alexa exige, mas não usaremos
                })
            }
            
        except Exception as e:
            print(f"Erro em /oauth/exchange: {str(e)}")
            return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': 'server_error'})}
    
    return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Rota não encontrada'})}