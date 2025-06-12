# Evolution API - Manual de Configuração

Este documento explica como configurar e usar o Evolution API para integração com WhatsApp no sistema Formulário Culsen.

## 📋 Índice

1. [Sobre o Evolution API](#sobre-o-evolution-api)
2. [Instalação](#instalação)
3. [Configuração](#configuração)
4. [Primeiro Uso](#primeiro-uso)
5. [Exemplos de Uso](#exemplos-de-uso)
6. [Troubleshooting](#troubleshooting)

## 🚀 Sobre o Evolution API

A Evolution API é uma API REST completa para integração com WhatsApp, permitindo:

- Envio de mensagens de texto, mídia, botões e listas
- Recebimento de mensagens via webhook
- Gerenciamento de grupos e contatos
- Status de delivery e leitura
- Upload de arquivos

## 📦 Instalação

### 1. Instalar Evolution API

Você pode instalar a Evolution API de várias formas:

#### Opção A: Docker (Recomendado)

```bash
# Clonar o repositório oficial
git clone https://github.com/EvolutionAPI/evolution-api.git
cd evolution-api

# Configurar variáveis de ambiente
cp .env.example .env

# Editar o arquivo .env conforme necessário
# Executar com Docker
docker-compose up -d
```

#### Opção B: NPM

```bash
npm install -g @evolution-api/api
evolution-api start
```

### 2. Configurar Dependências do Projeto

Adicione as dependências necessárias ao `requirements.txt`:

```bash
cd formulario_culsen
pip install python-dotenv
```

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` no diretório raiz do projeto ou configure as variáveis de ambiente:

```bash
# Copiar arquivo de exemplo
cp evolution_config_example.env .env

# Editar as configurações
nano .env
```

Configurações necessárias:

```env
# URL base da Evolution API
EVOLUTION_API_URL=http://localhost:8080

# Chave de API para autenticação
EVOLUTION_API_KEY=sua_chave_da_evolution_api_aqui

# Nome da instância do WhatsApp
EVOLUTION_INSTANCE_NAME=culsen_form

# URL do webhook para receber eventos (opcional)
EVOLUTION_WEBHOOK_URL=https://seu-dominio.com/webhook/evolution
```

### 2. Gerar Chave de API

Para gerar uma chave de API:

1. Acesse a interface web da Evolution API: `http://localhost:8080`
2. Vá em "Manager" > "API Key"
3. Gere uma nova chave
4. Copie a chave para a variável `EVOLUTION_API_KEY`

## 🎯 Primeiro Uso

### 1. Testar Configuração

Execute o script de teste para verificar se tudo está funcionando:

```bash
cd formulario_culsen
python test_evolution.py
```

### 2. Conectar WhatsApp

1. Execute o teste acima
2. Se aparecer um QR Code, escaneie com seu WhatsApp
3. Aguarde a confirmação de conexão

### 3. Exemplo Básico

```python
from utils.evopai import create_evolution_client

# Criar cliente
evolution = create_evolution_client()

# Verificar status
status = evolution.get_instance_status()
print(f"Status: {status}")

# Enviar mensagem de teste
number = evolution.format_phone_number("11999999999")
response = evolution.send_text_message(number, "Olá! Esta é uma mensagem de teste.")
print(f"Mensagem enviada: {response}")
```

## 💡 Exemplos de Uso

### Enviar Mensagem de Texto

```python
from utils.evopai import create_evolution_client

evolution = create_evolution_client()

# Formatear número
number = evolution.format_phone_number("11999999999")

# Enviar mensagem
response = evolution.send_text_message(
    number=number,
    message="Olá! Seu currículo foi recebido com sucesso."
)
```

### Enviar Mensagem com Mídia

```python
# Enviar imagem com legenda
response = evolution.send_media_message(
    number=number,
    media_url="https://exemplo.com/imagem.jpg",
    media_type="image",
    caption="Aqui está sua análise de currículo!"
)

# Enviar documento PDF
response = evolution.send_media_message(
    number=number,
    media_url="https://exemplo.com/curriculo_analisado.pdf",
    media_type="document",
    filename="Análise_Currículo.pdf"
)
```

### Enviar Mensagem com Botões

```python
buttons = [
    {
        "buttonId": "curriculo_aprovado",
        "buttonText": {"displayText": "✅ Aprovado"},
        "type": 1
    },
    {
        "buttonId": "curriculo_pendente",
        "buttonText": {"displayText": "⏳ Em Análise"},
        "type": 1
    }
]

response = evolution.send_button_message(
    number=number,
    text="Status do seu currículo:",
    buttons=buttons
)
```

### Enviar Lista de Opções

```python
sections = [
    {
        "title": "Vagas Disponíveis",
        "rows": [
            {
                "rowId": "vaga_dev",
                "title": "Desenvolvedor Python",
                "description": "Vaga para desenvolvedor Python sênior"
            },
            {
                "rowId": "vaga_analyst",
                "title": "Analista de Dados",
                "description": "Vaga para analista de dados pleno"
            }
        ]
    }
]

response = evolution.send_list_message(
    number=number,
    text="Vagas que combinam com seu perfil:",
    title="Oportunidades",
    button_text="Ver Vagas",
    sections=sections
)
```

### Integração com Formulário

```python
def notificar_candidato_whatsapp(telefone, nome, status_cv):
    """
    Notifica candidato via WhatsApp sobre status do CV
    """
    try:
        evolution = create_evolution_client()
        number = evolution.format_phone_number(telefone)
        
        if status_cv == "aprovado":
            message = f"🎉 Parabéns {nome}!\n\nSeu currículo foi APROVADO em nossa análise inicial.\n\nEm breve entraremos em contato para próximas etapas."
        elif status_cv == "em_analise":
            message = f"Olá {nome}!\n\n📋 Recebemos seu currículo e está em análise.\n\nVocê será notificado assim que tivermos uma resposta."
        else:
            message = f"Olá {nome}!\n\nAgradecemos seu interesse. Infelizmente seu perfil não se adequa às vagas atuais.\n\nContinue acompanhando nossas oportunidades!"
        
        response = evolution.send_text_message(number, message)
        return response
        
    except Exception as e:
        print(f"Erro ao enviar WhatsApp: {e}")
        return None
```

### Configurar Webhook

```python
# Configurar webhook para receber mensagens
webhook_url = "https://seu-dominio.com/webhook/evolution"
response = evolution.set_webhook(webhook_url)
```

### Processar Webhook (Flask)

```python
from flask import Flask, request, jsonify

@app.route('/webhook/evolution', methods=['POST'])
def evolution_webhook():
    data = request.json
    
    # Processar mensagem recebida
    if data.get('event') == 'messages.upsert':
        message = data.get('data', {})
        
        # Extrair informações
        from_number = message.get('key', {}).get('remoteJid', '')
        text = message.get('message', {}).get('conversation', '')
        
        # Processar comando
        if text.lower() == 'status':
            # Responder com status do currículo
            evolution = create_evolution_client()
            evolution.send_text_message(
                from_number, 
                "Consultando status do seu currículo..."
            )
    
    return jsonify({"status": "ok"})
```

## 🔧 Troubleshooting

### Problemas Comuns

#### 1. Erro de Conexão

```
❌ Erro ao criar cliente Evolution API: Connection refused
```

**Solução:**
- Verifique se a Evolution API está rodando
- Confirme se a URL está correta
- Teste: `curl http://localhost:8080/manager/health`

#### 2. Erro de Autenticação

```
❌ Erro ao obter status da instância: 401 Unauthorized
```

**Solução:**
- Verifique se `EVOLUTION_API_KEY` está correto
- Regenere a chave de API se necessário

#### 3. Instância Não Conectada

```
⚠️ WhatsApp não conectado - escaneie o QR Code
```

**Solução:**
- Execute: `python test_evolution.py`
- Escaneie o QR Code gerado
- Aguarde a confirmação de conexão

#### 4. Mensagem Não Enviada

```
❌ Erro ao enviar mensagem: Number not exists
```

**Solução:**
- Verifique se o número está correto
- Use o formato: `5511999999999@s.whatsapp.net`
- Confirme se o número tem WhatsApp ativo

### Logs e Debug

Para debug detalhado, configure o logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Verificar Status da API

```bash
# Verificar se a API está rodando
curl http://localhost:8080/manager/health

# Listar instâncias
curl -H "apikey: SUA_CHAVE" http://localhost:8080/instance/fetchInstances
```

## 📞 Suporte

Para mais informações:
- [Documentação Oficial Evolution API](https://doc.evolution-api.com/)
- [GitHub Evolution API](https://github.com/EvolutionAPI/evolution-api)
- [Discord da Comunidade](https://discord.gg/evolutionapi)

## 🚀 Próximos Passos

Após configurar com sucesso:

1. Integre o WhatsApp ao fluxo de análise de currículos
2. Configure webhooks para respostas automáticas
3. Implemente chatbot para triagem inicial
4. Configure notificações automáticas
5. Adicione templates de mensagem personalizados 